from dotenv import load_dotenv
import gradio as gr
from setup_AI_Assistant import GraphWorkflow
import asyncio
# import selectors
# import sys


load_dotenv(override=True)


async def setup():
    print("DEBUG: Instantiating GraphWorkflow...")
    assistant_object = GraphWorkflow()
    
    print("DEBUG: Awaiting assistant_object.setup()...")
    await assistant_object.setup()
    
    print("Setup complete")
    return assistant_object

async def process_message(gradio_state_object, user_message, history):
    result = await gradio_state_object.run_superstep(user_message, history)
    return result, gradio_state_object, ""

def free_resources(sidekick):
    if sidekick is None:
        return
        
    print("Cleaning up Assistant's resources...")
    try:
        # Get the current event loop to run the async cleanup
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(sidekick.cleanup())
        else:
            loop.run_until_complete(sidekick.cleanup())
    except Exception as e:
        print(f"Cleanup task failed: {e}")
    

# HF SPACE
# if __name__ == "__main__":
#     with gr.Blocks(title="AI Assistant", fill_width=True) as ui:
#         gr.Markdown("# Vantage AI")
#         gradio_state_object = gr.State(delete_callback=free_resources)
        
#         with gr.Row():
#             chat_messages = gr.Chatbot(label="AI Assistant", elem_classes="chat-container")
#         with gr.Row():
#             user_message = gr.Textbox(show_label=False, placeholder="Your query or task to the assistant", interactive=False)
#         with gr.Row():
#             go_button = gr.Button("Go!", variant="primary", interactive=False)
        
#         ui.load(setup,[],[gradio_state_object]).then(
#             lambda: (gr.update(interactive=True), gr.update(interactive=True)), None, [user_message, go_button]
#         )
#         user_message.submit(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message])
#         go_button.click(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message])
    
#     ui.launch(server_name="0.0.0.0", server_port=7860, show_error=True, css="""
#             .chat-container, .chat-container > div {
#             height: calc(100vh - 260px) !important;
#             max-height: calc(100vh - 260px) !important;
#         }
#     """)



# LOCAL
if __name__ == "__main__":
    with gr.Blocks(title="AI Assistant", fill_width=True) as ui:
        gr.Markdown("# Vantage AI")
        gradio_state_object = gr.State(delete_callback=free_resources)
        
        with gr.Row():
            chat_messages = gr.Chatbot(label="AI Assistant", elem_classes="chat-container")
        with gr.Row():
            user_message = gr.Textbox(show_label=False, placeholder="Your query or task to the assistant", interactive=False)
        with gr.Row():
            go_button = gr.Button("Go!", variant="primary", interactive=False)

        ui.load(setup,[],[gradio_state_object]).then(
            lambda: (gr.update(interactive=True), gr.update(interactive=True)), None, [user_message, go_button]
        )

        user_message.submit(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message])
        go_button.click(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message])

    ui.launch(inbrowser=True, css="""
            .chat-container, .chat-container > div {
            height: calc(100vh - 260px) !important;
            max-height: calc(100vh - 260px) !important;
        }
    """)



# WITH STATE object column
# if __name__ == "__main__":
#     with gr.Blocks(title="AI Assistant") as ui:
#         gr.Markdown("# Make your life easier with your custom AI Assistant")
#         gradio_state_object = gr.State(delete_callback=free_resources)

#         with gr.Row():
#                     with gr.Column(scale=3): # Left Column for Main Chat
#                         chat_messages = gr.Chatbot(label="AI Assistant", height=300)
#                         with gr.Row():
#                             user_message = gr.Textbox(show_label=False, placeholder="Your query or task to the assistant", interactive=False)
#                         with gr.Row():
#                             go_button = gr.Button("Go!", variant="primary", interactive=False)
                    
#                     with gr.Column(scale=2): # Right Column for Debugging Sidebar
#                         gr.Markdown("### Debugging Sidebar")
#                         # Added a Textbox to output the raw state object after every superstep
#                         state_raw = gr.Textbox(label="Messages", interactive=False, max_lines=25, autoscroll=True)
        

#         ui.load(setup,[],[gradio_state_object]).then(
#             lambda: (gr.update(interactive=True), gr.update(interactive=True)), None, [user_message, go_button]
#         )
#         user_message.submit(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message, state_raw])
#         go_button.click(process_message, [gradio_state_object, user_message, chat_messages], [chat_messages, gradio_state_object, user_message, state_raw])

#     ui.launch(inbrowser=True)