import streamlit as st
import tempfile
import os
import subprocess
import zipfile
from PIL import Image
import numpy as np
import fitz  # PyMuPDF
from skimage import filters, morphology, exposure, util, feature

# =========================
# PDF → PNG 変換
# =========================
def pdf_to_pngs(pdf_path):
    pdf = fitz.open(pdf_path)
    png_paths = []
    for page_num in range(len(pdf)):
        page = pdf.load_page(page_num)
        pix = page.get_pixmap(dpi=300)
        temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        pix.save(temp_png.name)
        png_paths.append(temp_png.name)
    return png_paths

# =========================
# 前処理（OpenCV 不使用）
# =========================
def preprocess_image(img_path, mode):
    img = Image.open(img_path).convert("L")
    img = np.array(img)

    if mode == "raw":
        return img

    if mode == "light":
        img = filters.gaussian(img, sigma=1)
        thresh = filters.threshold_otsu(img)
        return (img > thresh).astype(np.uint8) * 255

    if mode == "normal":
        img = filters.median(img, morphology.disk(2))
        img = exposure.equalize_adapthist(img)
        edges = feature.canny(img, sigma=1)
        return (edges * 255).astype(np.uint8)

    if mode == "strong":
        img = filters.median(img, morphology.disk(3))
        img = exposure.equalize_adapthist(img)
        edges = feature.canny(img, sigma=2)
        return (edges * 255).astype(np.uint8)

    if mode == "thinning":
        thresh = filters.threshold_otsu(img)
        binary = img > thresh
        thin = morphology.thin(binary)
        return (thin * 255).astype(np.uint8)

    return img

# =========================
# Potrace 自動最適化
# =========================
def auto_potrace_params(img):
    white_ratio = np.mean(img > 128)

    if white_ratio > 0.85:
        return {"turd": "5", "alpha": "0.5", "opt": "0.2"}
    elif white_ratio > 0.6:
        return {"turd": "3", "alpha": "0.7", "opt": "0.3"}
    else:
        return {"turd": "2", "alpha": "1.0", "opt": "0.4"}

# =========================
# PNG → SVG 変換
# =========================
def png_to_svg(png_path, mode="normal"):
    img = preprocess_image(png_path, mode)

    temp_bmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
    Image.fromarray(img).save(temp_bmp.name)

    params = auto_potrace_params(img)

    temp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")

    potrace_cmd = [
        "potrace", "-s", "-o", temp_svg.name,
        "--turdsize", params["turd"],
        "--alphamax", params["alpha"],
        "--opttolerance", params["opt"],
        temp_bmp.name
    ]

    subprocess.run(potrace_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return temp_svg.name

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="線画にせんか？", layout="wide")

st.title("✏️ 線画にせんか？")
st.write("PDF または画像を線画 SVG に変換します。（OpenCV 不使用・Cloud 完全対応）")

uploaded_file = st.file_uploader("PDF または PNG/JPG を選択", type=["pdf", "png", "jpg", "jpeg"])

mode = st.selectbox(
    "前処理モードを選択",
    ["なし（raw）", "軽め（light）", "標準（normal）", "強め（strong）", "細線化（thinning）"]
)

mode_key = {
    "なし（raw）": "raw",
    "軽め（light）": "light",
    "標準（normal）": "normal",
    "強め（strong）": "strong",
    "細線化（thinning）": "thinning"
}[mode]

if uploaded_file:
    st.success("ファイルを読み込みました！")

    temp_input = tempfile.NamedTemporaryFile(delete=False)
    temp_input.write(uploaded_file.read())
    temp_input.close()

    if uploaded_file.name.lower().endswith(".pdf"):
        png_list = pdf_to_pngs(temp_input.name)
    else:
        img = Image.open(temp_input.name)
        temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_png.name)
        png_list = [temp_png.name]

    st.write(f"ページ数：{len(png_list)}")

    if st.button("SVG に変換する"):
        svg_files = []

        progress = st.progress(0)
        for i, png in enumerate(png_list):
            svg_path = png_to_svg(png, mode_key)
            svg_files.append(svg_path)

            if i % 2 == 0:
                progress.progress((i + 1) / len(png_list))

        progress.progress(1.0)
        st.success("変換が完了しました！")

        zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for idx, svg in enumerate(svg_files):
                zipf.write(svg, arcname=f"page_{idx+1}.svg")

        with open(zip_path, "rb") as f:
            st.download_button(
                label="全ページを ZIP でダウンロード",
                data=f,
                file_name="all_pages.zip",
                mime="application/zip"
            )



