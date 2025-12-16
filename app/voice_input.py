import os
from sre_parse import State
import assemblyai as aai
from assemblyai.streaming.v3 import (
     BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)
from assemblyai.extras import MicrophoneStream
import logging
from typing import Dict, Type, Any
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

full_transcript_parts = []

def on_begin(self: Type[StreamingClient], event: BeginEvent):
    print(f"Session started: {event.id}")
    print("Speak now... (press Ctrl+C to stop)")

last_final_turn = ""

def on_turn(self: Type[StreamingClient], event: TurnEvent):
    global full_transcript_parts, last_final_turn

    if not event.transcript:
        return
    print(event.transcript, end=" ", flush=True)
    if event.end_of_turn and event.turn_is_formatted:
        text = event.transcript.strip()
        if text and text != last_final_turn:
            full_transcript_parts.append(text)
            last_final_turn = text
    if event.end_of_turn and not event.turn_is_formatted:
        params = StreamingSessionParameters(format_turns=True)
        self.set_params(params)


def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
    print(
        f"Session terminated: Processed {event.audio_duration_seconds:.1f} seconds of audio."
    )

def on_error(self: Type[StreamingClient], error: StreamingError):
    print(f"Error occurred: {error}")
    logger.error(f"Streaming error: {error}")


# Voice Input Handling Node
def voice_input_handler(state: Dict[str, Any]) -> Dict[str, Any]:
    global full_transcript_parts
    full_transcript_parts.clear()

    api_key = os.getenv("AssemblyAI_API_KEY")
    if not api_key:
        return {"error_message": "AssemblyAI API key is not set."}
    
    try:
        client = StreamingClient(
            StreamingClientOptions(
                api_key=api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)

        client.connect(
            StreamingParameters(
                sample_rate=16000,
                format_turns=True
            )
        )

        print("\nRecording started... Speak clearly into your laptop's built-in microphone.")
        print("Press Ctrl+C when you're done speaking.\n")
    
        try:
            stream = MicrophoneStream(sample_rate=16000)
            try:
                client.stream(stream)
            finally:
                stream.close()
        except KeyboardInterrupt:
            print("\n Voice recording stopped by user.")
        except Exception as mic_error:
            print(f"Microphone error: {mic_error}")
            return {"error_message": f"Microphone access failed: {mic_error}"}
        finally:
            try:
                client.disconnect(terminate=True)
            except Exception:
                pass

        user_voice_transcript = " ".join(full_transcript_parts).strip()
        
        if not user_voice_transcript:
            return {
                "error_message": "No speech detected. Transcript is empty.",
                "user_voice_transcript": ""
            }
        
        print(f"\n Full Transcript: \n{user_voice_transcript}\n")

        return {
            "user_voice_transcript": user_voice_transcript  
        }
    except Exception as e:
        logger.error(f"Unexpected error during voice input handling: {e}")
        return {"error_message": f"Voice input handling failed: {e}"}
