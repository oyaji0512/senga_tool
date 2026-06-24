import streamlit as st
import streamlit.components.v1 as components
import tempfile
import subprocess
import zipfile
from PIL import Image, ImageOps
import numpy as np
import fitz  # PyMuPDF
from skimage import filters, morphology, exposure, feature

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
# 写真 / 図面 自動判定
# =========================
def auto_detect_mode(img_path):
    img = Image.open(img_path).convert("L")
    arr = np.array(img)
    edges = feature.canny(arr, sigma=1)
    edge_density = np.mean(edges)
    brightness_std = np.std(arr)

    # エッジが多く明度変動が小さい → 図面(simple)
    # それ以外 → 写真(photo)
    if edge_density > 0.05 and brightness_std < 40:
        return "simple"
    else:
        return "photo"

# =========================
# AI補正付き 前処理
# =========================
def preprocess_image(
    img_path,
    mode,
    blur_sigma,
    edge_sigma,
    thickness,
    photo_auto,
    brightness,
    contrast,
    sharpness,
    denoise,
):
    img = Image.open(img_path).convert("L")
    img = np.array(img)

    # 共通ぼかし（ノイズ除去）
    if blur_sigma > 0:
        img = filters.gaussian(img, sigma=blur_sigma)

    # モード別処理
    if mode == "raw":
        processed = img

    elif mode == "light":
        thresh = filters.threshold_otsu(img)
        processed = (img > thresh).astype(np.uint8) * 255

    elif mode == "normal":
        img_m = filters.median(img, morphology.disk(2))
        img_m = exposure.equalize_adapthist(img_m)
        edges = feature.canny(img_m, sigma=edge_sigma)
        processed = (edges * 255).astype(np.uint8)

    elif mode == "strong":
        img_m = filters.median(img, morphology.disk(3))
        img_m = exposure.equalize_adapthist(img_m)
        edges = feature.canny(img_m, sigma=edge_sigma + 1)
        processed = (edges * 255).astype(np.uint8)

    elif mode == "thinning":
        thresh = filters.threshold_otsu(img)
        binary = img > thresh
        thin = morphology.thin(binary)
        processed = (thin * 255).astype(np.uint8)

    elif mode == "simple":
        # CAD図面向け：高速・クッキリ
        thresh = filters.threshold_otsu(img)
        binary = img > thresh
        processed = (binary * 255).astype(np.uint8)

    elif mode == "photo":
        # 写真用リアル線画：細部も残す
        img_f = img.astype(np.float32) / 255.0

        # 写真用自動補正
        if photo_auto:
            img_f = exposure.equalize_adapthist(img_f)

        # 写真専用ノイズ除去
        if denoise > 0:
            img_f = filters.gaussian(img_f, sigma=denoise)

        # 明るさ補正
        img_f = np.clip(img_f * brightness, 0.0, 1.0)

        # コントラスト補正（ガンマ）
        img_f = exposure.adjust_gamma(img_f, contrast)

        # シャープネス（アンシャープマスク）
        if sharpness > 0:
            img_f = filters.unsharp_mask(img_f, radius=1.0, amount=sharpness)

        edges = feature.canny(img_f, sigma=edge_sigma)
        processed = (edges * 255).astype(np.uint8)

    else:
        processed = img

    # 太さ調整（膨張）
    if thickness > 0:
        processed = morphology.dilation(processed, morphology.disk(thickness))

    return processed

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
def png_to_svg(
    png_path,
    mode,
    blur_sigma,
    edge_sigma,
    thickness,
    photo_auto,
    brightness,
    contrast,
    sharpness,
    denoise,
):
    img = preprocess_image(
        png_path,
        mode,
        blur_sigma,
        edge_sigma,
        thickness,
        photo_auto,
        brightness,
        contrast,
        sharpness,
        denoise,
    )

    temp_bmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
    Image.fromarray(img).save(temp_bmp.name)

    params = auto_potrace_params(img)

    temp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")

    potrace_cmd = [
        "potrace",
        "-s",
        "-o",
        temp_svg.name,
        "--turdsize",
        params["turd"],
        "--alphamax",
        params["alpha"],
        "--opttolerance",
        params["opt"],
        temp_bmp.name,
    ]

    subprocess.run(potrace_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return temp_svg.name

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="線画にせんか？", layout="wide")

st.title("✏️ 線画にせんか？（自動判定＋SVGプレビュー版）")
st.write("PDF / 画像を線画 SVG に変換します。図面・写真を自動判定し、結果SVGもプレビューできます。")

uploaded_file = st.file_uploader("PDF または PNG/JPG を選択", type=["pdf", "png", "jpg", "jpeg"])

# 前処理モード（手動選択用）
mode_label = st.selectbox(
    "前処理モード（手動指定）",
    [
        "なし（raw）",
        "軽め（light）",
        "標準（normal）",
        "強め（strong）",
        "細線化（thinning）",
        "簡易版（simple）",
        "写真用（photo）",
    ],
)

label_to_key = {
    "なし（raw）": "raw",
    "軽め（light）": "light",
    "標準（normal）": "normal",
    "強め（strong）": "strong",
    "細線化（thinning）": "thinning",
    "簡易版（simple）": "simple",
    "写真用（photo）": "photo",
}
key_to_label = {v: k for k, v in label_to_key.items()}
mode_key_manual = label_to_key[mode_label]

# 共通AI補正スライダー
st.subheader("AI補正（共通）")
blur_sigma = st.slider("ぼかし量（共通ノイズ除去）", 0.0, 3.0, 0.0, 0.1)
edge_sigma = st.slider("エッジ強調（Canny σ）", 0.5, 3.0, 1.0, 0.1)
thickness = st.slider("線の太さ（膨張）", 0, 5, 0)
photo_auto = st.checkbox("写真用自動補正を有効にする（Photo Auto Enhance）", value=True)

# 写真モード専用スライダー（値の入れ物を先に用意）
brightness = 1.0
contrast = 1.0
sharpness = 0.0
denoise = 0.0

if uploaded_file:
    st.success("ファイルを読み込みました！")

    # 一時ファイルに保存
    temp_input = tempfile.NamedTemporaryFile(delete=False)
    temp_input.write(uploaded_file.read())
    temp_input.close()

    # PDF or Image → PNG list
    if uploaded_file.name.lower().endswith(".pdf"):
        png_list = pdf_to_pngs(temp_input.name)
    else:
        img = Image.open(temp_input.name)
        temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_png.name)
        png_list = [temp_png.name]

    st.write(f"ページ数：{len(png_list)}")

    # 自動判定（先頭ページで判定）
    auto_mode_key = auto_detect_mode(png_list[0])
    auto_mode_label = key_to_label[auto_mode_key]
    st.info(f"自動判定結果：このファイルは「{auto_mode_label}」っぽいです。")

    use_auto = st.checkbox("自動判定モードを優先する", value=True)

    # 実際に使うモードキー
    effective_mode_key = auto_mode_key if use_auto else mode_key_manual
    effective_mode_label = key_to_label.get(effective_mode_key, mode_label)

    st.write(f"現在使用中のモード：**{effective_mode_label}**")

    # 写真モード専用スライダー（effective_mode が photo のときだけ表示）
    if effective_mode_key == "photo":
        st.subheader("写真補正スライダー")
        brightness = st.slider("明るさ補正", 0.5, 2.0, 1.0, 0.1)
        contrast = st.slider("コントラスト補正（γ）", 0.5, 2.0, 1.0, 0.1)
        sharpness = st.slider("シャープネス", 0.0, 3.0, 1.0, 0.1)
        denoise = st.slider("写真用ノイズ除去", 0.0, 3.0, 0.0, 0.1)

    # ページ切り替え
    page = st.number_input("プレビューするページを選択", 1, len(png_list), 1)

    # 線画プレビュー生成
    processed = preprocess_image(
        png_list[page - 1],
        effective_mode_key,
        blur_sigma,
        edge_sigma,
        thickness,
        photo_auto,
        brightness,
        contrast,
        sharpness,
        denoise,
    )
    preview_img = Image.fromarray(processed)

    # 写真モードのときは白背景に黒線に揃える
    if effective_mode_key == "photo":
        preview_img = ImageOps.invert(preview_img)

    # 背景色切り替え
    bg_option = st.radio("背景色を選択", ["白（デフォルト）", "黒", "反転"])
    base_img = preview_img.convert("RGB")

    if bg_option == "白（デフォルト）":
        shown_img = base_img
    else:
        shown_img = ImageOps.invert(base_img)

    st.subheader("プレビュー")
    st.image(
        shown_img,
        caption=f"{page} ページ目のプレビュー（{effective_mode_label} / {bg_option}）",
        use_column_width=True,
    )

    # SVG変換（全ページ）
    if st.button("SVG に変換する"):
        svg_files = []
        progress = st.progress(0)

        for i, png in enumerate(png_list):
            svg_path = png_to_svg(
                png,
                effective_mode_key,
                blur_sigma,
                edge_sigma,
                thickness,
                photo_auto,
                brightness,
                contrast,
                sharpness,
                denoise,
            )
            svg_files.append(svg_path)
            progress.progress((i + 1) / len(png_list))

        st.success("変換が完了しました！")

        # SVGプレビュー（先頭ページ）
        st.subheader("SVGプレビュー（1ページ目）")
        try:
            with open(svg_files[0], "r", encoding="utf-8") as f:
                svg_content = f.read()
            components.html(svg_content, height=600, scrolling=True)
        except Exception as e:
            st.warning(f"SVGプレビューの読み込みに失敗しました: {e}")

        # ZIPダウンロード
        zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for idx, svg in enumerate(svg_files):
                zipf.write(svg, arcname=f"page_{idx+1}.svg")

        with open(zip_path, "rb") as f:
            st.download_button(
                label="全ページを ZIP でダウンロード",
                data=f,
                file_name="all_pages.zip",
                mime="application/zip",
            )
