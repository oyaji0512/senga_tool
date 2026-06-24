import streamlit as st
import tempfile
import os
import subprocess
import zipfile
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np

# =========================
# PDF → PNG 変換（PyMuPDF）
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
# OpenCV 前処理
# =========================
def preprocess_image(img_path, mode):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)

    if mode == "raw":
        return img

    # 軽め
    if mode == "light":
        img = cv2.GaussianBlur(img, (3, 3), 0)
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return img

    # 標準
    if mode == "normal":
        img = cv2.medianBlur(img, 3)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe.apply(img)
        img = cv2.Laplacian(img, cv2.CV_8U)
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        return img

    # 強め
    if mode == "strong":
        img = cv2.medianBlur(img, 5)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        img = clahe.apply(img)
        img = cv2.Laplacian(img, cv2.CV_8U)
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((3, 3), np.uint8)
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
        return img

    # 細線化（Zhang-Suen）
    if mode == "thinning":
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.ximgproc.thinning(img)
        return img

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
# PNG → SVG 変換（Potrace）
# =========================
def png_to_svg(png_path, mode="normal"):
    # OpenCV 前処理
    img = preprocess_image(png_path, mode)

    # 一時BMP保存
    temp_bmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
    cv2.imwrite(temp_bmp.name, img)

    # Potrace 自動パラメータ
    params = auto_potrace_params(img)

    temp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")

    potrace_cmd = [
        "potrace",
        "-s",
        "-o", temp_svg.name,
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
st.write("PDF または画像を線画 SVG に変換します。")

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
            progress.progress((i + 1) / len(png_list))

        st.success("変換が完了しました！")

        for idx, svg in enumerate(svg_files):
            with open(svg, "rb") as f:
                st.download_button(
                    label=f"ページ {idx+1} をダウンロード（SVG）",
                    data=f,
                    file_name=f"page_{idx+1}.svg",
                    mime="image/svg+xml"
                )

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
