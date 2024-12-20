import json
import uuid
import random
import base64
import urllib
import websocket
from PIL import Image, ImageOps
import streamlit as st
from st_clickable_images import clickable_images
from requests_toolbelt import MultipartEncoder


def open_websocket_connection():
    server_address = "127.0.0.1:8188"
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    return ws, server_address, client_id


def upload_image(image_data, name, server_address, image_type="input", overwrite=False):
    multipart_data = MultipartEncoder(
        fields={
            "image": (name, image_data, "image/png"),
            "type": image_type,
            "overwrite": str(overwrite).lower(),
        }
    )

    data = multipart_data
    headers = {"Content-Type": multipart_data.content_type}
    request = urllib.request.Request(
        "http://{}/upload/image".format(server_address), data=data, headers=headers
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def load_workflow(workflow_path):
    try:
        with open(workflow_path, "r") as file:
            workflow = json.load(file)
            return workflow
    except FileNotFoundError:
        print(f"The file {workflow_path} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"The file {workflow_path} contains invalid JSON.")
        return None


def queue_prompt(prompt, client_id, server_address):
    p = {"prompt": prompt, "client_id": client_id}
    headers = {"Content-Type": "application/json"}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request(
        "http://{}/prompt".format(server_address), data=data, headers=headers
    )
    return json.loads(urllib.request.urlopen(req).read())


def track_progress(prompt, ws, prompt_id, progress_bar, progress_text):
    node_ids = list(prompt.keys())
    finished_nodes = []

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "progress":
                data = message["data"]
                current_step = data["value"]
                print("In K-Sampler -> Step: ", current_step, " of: ", data["max"])
            if message["type"] == "execution_cached":
                data = message["data"]
                for itm in data["nodes"]:
                    if itm not in finished_nodes:
                        finished_nodes.append(itm)
                        print(
                            "Progess: ",
                            len(finished_nodes),
                            "/",
                            len(node_ids),
                            " Tasks done",
                        )
                        progress_bar.progress(
                            len(finished_nodes) / len(node_ids), text=progress_text
                        )
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] not in finished_nodes:
                    finished_nodes.append(data["node"])
                    print(
                        "Progess: ",
                        len(finished_nodes),
                        "/",
                        len(node_ids),
                        " Tasks done",
                    )
                    progress_bar.progress(
                        len(finished_nodes) / len(node_ids), text=progress_text
                    )

                if data["node"] is None and data["prompt_id"] == prompt_id:
                    progress_bar.empty()
                    break  # Execution is done
        else:
            continue
    return


def get_history(prompt_id, server_address):
    with urllib.request.urlopen(
        "http://{}/history/{}".format(server_address, prompt_id)
    ) as response:
        return json.loads(response.read())


def get_image(filename, subfolder, folder_type, server_address):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(
        "http://{}/view?{}".format(server_address, url_values)
    ) as response:
        return response.read()


def get_images(prompt_id, server_address, allow_preview=False):
    output_images = []

    history = get_history(prompt_id, server_address)[prompt_id]
    for node_id in history["outputs"]:
        node_output = history["outputs"][node_id]
        output_data = {}
        if "images" in node_output:
            for image in node_output["images"]:
                if allow_preview and image["type"] == "temp":
                    preview_data = get_image(
                        image["filename"],
                        image["subfolder"],
                        image["type"],
                        server_address,
                    )
                    output_data["image_data"] = preview_data
                if image["type"] == "output":
                    image_data = get_image(
                        image["filename"],
                        image["subfolder"],
                        image["type"],
                        server_address,
                    )
                    output_data["image_data"] = image_data
                output_data["file_name"] = image["filename"]
                output_data["type"] = image["type"]
                output_images.append(output_data)

    return output_images


workflow_path = "./assets/mannequin-to-model.json"
prompt = load_workflow(workflow_path)

if st.session_state.get("icon") is not None:
    icon = st.session_state["icon"]
else:
    icon = Image.open("./assets/faishme.png")
    st.session_state["icon"] = icon

st.set_page_config(
    page_title="AI for Your Fashion",
    page_icon=icon,
)

example_files = [
    "./assets/3062bb2968dd41a79ef07d654a6103b4.jpg",
    "./assets/11371d01bfdb46f58a6a5cc4e273d611.jpg",
    "./assets/e0f6611f46c44fd598c6dd515895b682.jpg",
    "./assets/b5d2993bbf98461fa7f21e42adf4bb79.jpg",
    "./assets/barca-shirt.png",
]

female_models_list = ["Disha", "Nandani", "Anamika", "Amelia", "Olivia"]
male_models_list = ["Ishan", "Leonardo"]

model_details = {
    "Amelia": {"lora": "am3l14.safetensors", "image": "./assets/female/amelia.jpeg"},
    "Anamika": {"lora": "an4m1k4.safetensors", "image": "./assets/female/anamika.jpeg"},
    "Disha": {"lora": "d1sh4.safetensors", "image": "./assets/female/disha.jpeg"},
    "Nandani": {"lora": "n4nd4n1.safetensors", "image": "./assets/female/nandani.jpeg"},
    "Olivia": {"lora": "ol1v14.safetensors", "image": "./assets/female/olivia.jpeg"},
    "Ishan": {"lora": "i6h4n.safetensors", "image": "./assets/male/ishan.jpeg"},
    "Leonardo": {
        "lora": "l3on4rd0.safetensors",
        "image": "./assets/male/leonardo.jpeg",
    },
}


# Sidebar
with st.sidebar:
    st.image(icon)
    st.subheader("AI for Your Fashion")

    gender = st.selectbox(
        "Choose model's gender",
        ("Female", "Male"),
    )
    if gender == "Female":
        ethnicity = st.selectbox("Choose fashion model", female_models_list)
    else:
        ethnicity = st.selectbox("Choose fashion model", male_models_list)

    st.subheader("Available fashion models")
    col1, col2 = st.columns(2)
    models_list = female_models_list if gender == "Female" else male_models_list
    with col1:
        for name in models_list[::2]:
            st.markdown(
                f'<div style="text-align: center;">{name}</div>',
                unsafe_allow_html=True,
            )
            st.image(model_details[name]["image"])
    with col2:
        for name in models_list[1::2]:
            st.markdown(
                f'<div style="text-align: center;">{name}</div>',
                unsafe_allow_html=True,
            )
            st.image(model_details[name]["image"])

    st.subheader(":arrow_up: Upload Flatlay T-shirt image")
    uploaded_file = st.file_uploader("Choose image file", accept_multiple_files=False)

    gender = st.selectbox(
        "Pose hint",
        ("Front", "Side", "Back"),
    )

# Body
st.header("Faishme - AI for your Fashion")
st.write(
    "Input instructions: This is a basic proof of concept to showcase our product. Currently, the demo only supports flatlay images of collarless t-shirts. The images should be well-lit with a distinct background, ensuring the garment is clearly visible. Users can upload the flatlay image from the left sidebar and specify the fashion model's ethnicity and gender. As this is a very preliminary product, we currently handle generation requests sequentially, so the process might take some time"
)

col1, col2 = st.columns(2)
output = None

if uploaded_file is not None:
    input_image = uploaded_file.getvalue()
    filename = uploaded_file.name

    with col1:
        st.subheader(":camera: Input")
        st.image(ImageOps.exif_transpose(Image.open(uploaded_file)))

        if st.button(":arrows_counterclockwise: Generate"):
            try:
                ws, server_address, client_id = open_websocket_connection()
                res = upload_image(input_image, filename, server_address)
                filename = res["name"]
                print("Uploaded file name", filename)

                prompt["101"]["inputs"]["lora_name"] = prompt["109"]["inputs"][
                    "lora_name"
                ] = "d1sh4.safetensors"
                prompt["101"]["inputs"]["pose_hint"] = "front"
                prompt["21"]["inputs"]["image"] = filename
                prompt["12"]["inputs"]["seed"] = random.randint(10**14, 10**15 - 1)
                prompt["46"]["inputs"]["seed"] = random.randint(10**14, 10**15 - 1)
                prompt["63"]["inputs"]["seed"] = random.randint(10**14, 10**15 - 1)
                prompt["122"]["inputs"]["seed"] = random.randint(10**14, 10**15 - 1)

                res = queue_prompt(prompt, client_id, server_address)
                prompt_id = res["prompt_id"]
                progress_text = "Generating image. Please wait..."
                progress_bar = st.progress(0, text=progress_text)

                track_progress(prompt, ws, prompt_id, progress_bar, progress_text)
                images = get_images(prompt_id, server_address, False)
                # output_path = "./output"
                # save_image(images, output_path, False)
                output = images[-1]["image_data"]
            finally:
                ws.close()

    if output is not None:
        with col2:
            st.subheader(":tshirt: Output")
            st.image(output)
