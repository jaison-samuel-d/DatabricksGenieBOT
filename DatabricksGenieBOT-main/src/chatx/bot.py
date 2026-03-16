import asyncio
import json
import logging

from botbuilder.core import ActivityHandler, TurnContext, ConversationState, UserState
from botbuilder.dialogs import Dialog
from botbuilder.schema import ChannelAccount, TokenResponse

from chatx.adaptive_card import AdaptiveCardFactory
from chatx.recommendations import (
    generate_contextual_recommendations,
    get_error_recovery_suggestions,
)
from chatx.const import (
    SPACE_NOT_FOUND,
    SWITCHING_MESSAGE,
    REVERSE_SPACES,
    WELCOME_MESSAGE,
    LOGIN_REQUIRED_MESSAGE,
    SPACES,
    DEFAULT_SPACE_ID,
    OAUTH_CONNECTION_NAME,
)
from chatx.genie import GenieQuerier
from chatx.helpers.dialog_helper import DialogHelper

# Log
logger = logging.getLogger(__name__)


class MyBot(ActivityHandler):
    # conversation_ids: dict[str, str]
    # space_ids: dict[str, str]
    # genie_querier: GenieQuerier

    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        dialog: Dialog,
        auth_method: str = "oauth",
    ):
        self.conversation_ids: dict[str, str | None] = {}
        self.space_ids: dict[str, str] = {}
        self.genie_querier: dict[str, GenieQuerier] = {}
        self.last_questions: dict[str, str] = {}
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.dialog = dialog
        assert auth_method in ["oauth", "service_principal"], (
            "auth_method should be one of ['oauth','service_principal']"
        )
        self.auth_method = auth_method

    async def on_message_activity(self, turn_context: TurnContext):
        """
        Handles incoming messages from the user.
        It processes the message, determines the appropriate Genie space,
        and sends the query to Genie for processing.
        :param turn_context: The context of the turn, containing the activity.
        :return: None
        """
        logger.info(
            f"on_message_activity: Received message: {turn_context.activity.text}"
        )

        if not turn_context.activity.from_property or not isinstance(
            turn_context.activity.from_property.id, str
        ):
            logger.warning("No valid user identifier found")
            await turn_context.send_activity(
                "Unable to identify user. Please try again."
            )
            return

        question = turn_context.activity.text
        user_id = str(turn_context.activity.from_property.id)
        conversation_id = self.conversation_ids.get(user_id)
        space_id = self.space_ids.get(user_id) or DEFAULT_SPACE_ID

        # Check if genie has been initialized
        if self.genie_querier.get(user_id) is None:
            self.genie_querier[user_id] = GenieQuerier()

        if self.genie_querier[user_id].auth_method is None:
            if self.auth_method == "oauth":
                # Match video UX: ask user to type "login" before showing OAuth card
                if question.strip().lower() not in ("login", "sign in", "signin"):
                    await turn_context.send_activity(LOGIN_REQUIRED_MESSAGE)
                    return
                logger.info("User requested login, triggering OAuth dialog")
                await self._trigger_login_dialog(turn_context)
                return
            elif self.auth_method == "service_principal":
                logger.error(
                    "DATABRICKS_CLIENT_ID or DATABRICKS_CLIENT_SECRET missing in App settings"
                )
                await turn_context.send_activity(
                    "Bot misconfigured: Databricks credentials (DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET) are required. Please contact the administrator."
                )
                return

        elif self.genie_querier[user_id].auth_method == "service_principal":
            if self.auth_method == "oauth":
                logger.warning(
                    "GenieQuerier initialized with SP credentials, prompting user to login"
                )
                await self._trigger_login_dialog(turn_context)
                return await self._initialize_genie_querier_with_token(
                    turn_context, user_id
                )

        # Trigger login - in case token has timed out.
        if self.auth_method == "oauth":
            await self._trigger_login_dialog(turn_context)

        # Check if genie has been initialized
        if "logout" in question.lower():
            await turn_context.send_activity("Logging you out.")
            self.genie_querier[user_id] = GenieQuerier()  # reset the genie querier
            return await turn_context.adapter.sign_out_user(
                turn_context, OAUTH_CONNECTION_NAME, None
            )

        elif SWITCHING_MESSAGE in question.lower():
            space_id = get_space_id(question)
            if space_id == SPACE_NOT_FOUND:
                return await turn_context.send_activity(SPACE_NOT_FOUND)

            self.space_ids[user_id] = space_id
            # Reset conversation ID for the new space
            self.conversation_ids.pop(user_id, None)
            await turn_context.send_activity(
                f"Switched to {REVERSE_SPACES[space_id]}. What would you like to explore?"
            )
            await turn_context.send_activity(
                AdaptiveCardFactory.get_recommendation_activity()
            )
        else:
            if not space_id or "@" in question.lower():
                new_space_id = get_space_id(question)
                if new_space_id == SPACE_NOT_FOUND:
                    return await turn_context.send_activity(SPACE_NOT_FOUND)

                # users want to switch spaces
                if new_space_id != space_id:
                    space_id = new_space_id
                    conversation_id = None
                    self.space_ids[user_id] = new_space_id
                    self.conversation_ids.pop(user_id, None)
                    await turn_context.send_activity(
                        f"Switched to {REVERSE_SPACES[space_id]}. Ask me anything about the data."
                    )
            try:
                wait_activity = await turn_context.send_activity(
                    AdaptiveCardFactory.get_waiting_message(step=1)
                )

                async def update_loader_steps():
                    for s in [2, 3]:
                        await asyncio.sleep(2.5)
                        try:
                            step_card = AdaptiveCardFactory.get_waiting_message(step=s)
                            step_card.id = wait_activity.id
                            await turn_context.update_activity(step_card)
                        except Exception:
                            break

                loader_task = asyncio.create_task(update_loader_steps())
                try:
                    genie_result = await self.genie_querier[user_id].ask_genie(
                        question, space_id, conversation_id
                    )
                finally:
                    loader_task.cancel()
                    try:
                        await loader_task
                    except asyncio.CancelledError:
                        pass

                self.conversation_ids[user_id] = genie_result.conversation_id
                self.last_questions[user_id] = question

                response_activity = genie_result.process_query_results()
                response_activity.id = wait_activity.id

                followups = getattr(response_activity, "followup_questions", None)
                contextual_recs = generate_contextual_recommendations(
                    question, genie_result.genie_answer or "", followups
                )

                if not genie_result.statement_response:
                    rec = AdaptiveCardFactory.get_recommendation_activity(
                        "What else would you like to know?",
                        questions=contextual_recs,
                    )
                    response_activity.suggested_actions = rec.suggested_actions

                await turn_context.update_activity(response_activity)

                if genie_result.statement_response:
                    await turn_context.send_activity(
                        AdaptiveCardFactory.get_recommendation_activity(
                            "What else would you like to know?",
                            questions=contextual_recs,
                        )
                    )
                return

            except json.JSONDecodeError:
                suggestions = get_error_recovery_suggestions("json")
                await turn_context.send_activity(
                    AdaptiveCardFactory.get_error_recovery_activity(
                        "Something went wrong on my end. Could you try asking again?",
                        suggestions,
                    )
                )
                await turn_context.send_activity(
                    AdaptiveCardFactory.get_recommendation_activity(
                        questions=generate_contextual_recommendations(
                            self.last_questions.get(user_id, ""),
                        ),
                    )
                )
            except Exception as e:
                if "This channel does not support this operation" in str(e):
                    try:
                        resp = genie_result.process_query_results()
                        followups = getattr(resp, "followup_questions", None)
                        contextual_recs = generate_contextual_recommendations(
                            question, genie_result.genie_answer or "", followups
                        )
                        if not genie_result.statement_response:
                            rec = AdaptiveCardFactory.get_recommendation_activity(
                                "What else would you like to know?",
                                questions=contextual_recs,
                            )
                            resp.suggested_actions = rec.suggested_actions
                        await turn_context.send_activity(resp)
                        if genie_result.statement_response:
                            await turn_context.send_activity(
                                AdaptiveCardFactory.get_recommendation_activity(
                                    "What else would you like to know?",
                                    questions=contextual_recs,
                                )
                            )
                        return
                    except (NameError, AttributeError, UnboundLocalError):
                        pass
                logger.error(f"Error processing message: {str(e)}")
                suggestions = get_error_recovery_suggestions("generic")
                await turn_context.send_activity(
                    AdaptiveCardFactory.get_error_recovery_activity(
                        "I ran into an issue. Please try rephrasing your question or ask again in a moment.",
                        suggestions,
                    )
                )
                await turn_context.send_activity(
                    AdaptiveCardFactory.get_recommendation_activity(
                        questions=generate_contextual_recommendations(
                            self.last_questions.get(user_id, ""),
                        ),
                    )
                )
                return

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                logger.debug(
                    f"on_members_added_activity: Member added, initializing genie querier for user: {member.id}"
                )
                self.genie_querier[member.id] = GenieQuerier()
                await turn_context.send_activity(WELCOME_MESSAGE)
                await turn_context.send_activity(
                    AdaptiveCardFactory.get_recommendation_activity()
                )

    async def on_turn(self, turn_context: TurnContext):
        await super().on_turn(turn_context)

        # Save any state changes that might have occurred during the turn.
        await self.conversation_state.save_changes(turn_context, False)
        await self.user_state.save_changes(turn_context, False)

    # Handle token response for web chat
    async def on_token_response_event(self, turn_context: TurnContext):
        logger.info("on_token_response_event: Token response event received")

        # Extract the token from the activity value
        token_response = TokenResponse().deserialize(turn_context.activity.value)
        user_id = str(turn_context.activity.from_property.id)

        if token_response and token_response.token:
            logger.info(
                "on_token_response_event: Token received successfully, initializing GenieQuerier"
            )
            # Initialize the genie querier with the token
            self.genie_querier[user_id] = GenieQuerier(token=token_response.token)
        else:
            logger.error(
                "on_token_response_event: No token found in token response event"
            )
            await turn_context.send_activity("Authentication failed. Please try again.")
            return

        # Run the Dialog with the new Token Response Event Activity.
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )
        return await turn_context.send_activity(
            "(TokenResponse) Successfully logged in"
        )

    # Handle teams signin/verifyState invoke activity
    async def on_teams_signin_verify_state(self, turn_context: TurnContext):
        # Run the Dialog with the new Token Response Event Activity.
        # The OAuth Prompt needs to see the Invoke Activity in order to complete the login process.
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )

        user_id = str(turn_context.activity.from_property.id)
        # After successful authentication, try to get the token and initialize genie querier
        await self._initialize_genie_querier_with_token(turn_context, user_id)
        return await turn_context.send_activity(
            "(TeamsVerifyState) Successfully logged in"
        )

    # on_invoke_activity does not handle signin/verifyState, so we need to handle it here
    async def on_invoke_activity(self, turn_context: TurnContext):
        if turn_context.activity.name == "signin/verifyState":
            return await self.on_teams_signin_verify_state(turn_context)
        # Handle recommendation card Action.Submit (Web Chat sends invoke)
        if turn_context.activity.name == "adaptiveCard/action":
            value = getattr(turn_context.activity, "value", None) or {}
            if isinstance(value, dict):
                # Handle recommendation question
                question = value.get("question")
                if question:
                    turn_context.activity.text = question
                    return await self.on_message_activity(turn_context)
        return await super().on_invoke_activity(turn_context)

    async def _initialize_genie_querier_with_token(
        self, turn_context: TurnContext, user_id: str
    ):
        """
        Initialize the genie querier with the user's token.
        :param turn_context: The context of the turn.
        """
        try:
            # Try to get the token from the adapter
            token_response = await turn_context.adapter.get_user_token(
                turn_context, OAUTH_CONNECTION_NAME
            )

            if token_response and token_response.token:
                logger.info(
                    "_initialize_genie_querier_with_token: Token retrieved successfully, initializing GenieQuerier"
                )
                self.genie_querier[user_id] = GenieQuerier(token=token_response.token)
            else:
                logger.warning(
                    "_initialize_genie_querier_with_token: No token available for genie querier initialization"
                )
        except Exception as e:
            logger.error(f"Error initializing genie querier with token: {str(e)}")

    async def _is_user_authenticated(self, turn_context: TurnContext) -> bool:
        """
        Check if the user is authenticated by attempting to get their token.
        :param turn_context: The context of the turn.
        :return: True if authenticated, False otherwise.
        """
        try:
            token_response = await turn_context.adapter.get_user_token(
                turn_context, OAUTH_CONNECTION_NAME
            )
            return token_response is not None and token_response.token is not None
        except Exception as e:
            logger.error(f"Error checking authentication: {str(e)}")
            return False

    async def _trigger_login_dialog(self, turn_context: TurnContext):
        """
        Trigger the login dialog to authenticate the user.
        :param turn_context: The context of the turn.
        """
        try:
            return await DialogHelper.run_dialog(
                self.dialog,
                turn_context,
                self.conversation_state.create_property("DialogState"),
            )
        except Exception as e:
            logger.error(
                f"_trigger_login_dialog: Error triggering login dialog: {str(e)}"
            )
            await turn_context.send_activity(
                "An error occurred while trying to authenticate. Please try again."
            )


def get_space_id(question: str) -> str:
    """
    Determines the Genie space ID based on the question.
    :param question: The question to analyze for space ID.
    :return: The space ID if found, otherwise a message indicating space not found.
    """
    for space_name, space_id in SPACES.items():
        if "@" + space_name.lower() in question.lower():
            return space_id
    return SPACE_NOT_FOUND
