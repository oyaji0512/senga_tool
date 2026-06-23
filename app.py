import streamlit as st
import tempfile
import os
import subprocess
import zipfile
from PIL import Image
import fitz  # PyMuPDF

# =========================
# PDF → PNG 変換（Poppler）
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
# PNG → SVG 変換（Potrace）
# =========================
def png_to_svg(png_path, mode="normal"):
    temp_bmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
    temp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")

    # mkbitmap（前処理）
    mkbitmap_cmd = [
        "mkbitmap",
        "-o", temp_bmp.name,
        png_path
    ]

    # モード別のパラメータ
    if mode == "light":
        mkbitmap_cmd.insert(1, "-t")
        mkbitmap_cmd.insert(2, "0.45")
    elif mode == "strong":
        mkbitmap_cmd.insert(1, "-t")
        mkbitmap_cmd.insert(2, "0.65")

    subprocess.run(mkbitmap_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # potrace（SVG 生成）
    potrace_cmd = [
        "potrace",
        "-s",
        "-o", temp_svg.name,
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
    "線画モードを選択",
    ["標準（normal）", "明るめ（light）", "濃いめ（strong）"]
)

mode_key = {
    "標準（normal）": "normal",
    "明るめ（light）": "light",
    "濃いめ（strong）": "strong"
}[mode]

if uploaded_file:
    st.success("ファイルを読み込みました！")

    # 一時保存
    temp_input = tempfile.NamedTemporaryFile(delete=False)
    temp_input.write(uploaded_file.read())
    temp_input.close()

    # PDF or 画像判定
    if uploaded_file.name.lower().endswith(".pdf"):
        png_list = pdf_to_pngs(temp_input.name)
    else:
        img = Image.open(temp_input.name)
        temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_png.name)
        png_list = [temp_png.name]

    st.write(f"ページ数：{len(png_list)}")

    # 変換ボタン
    if st.button("SVG に変換する"):
        svg_files = []

        progress = st.progress(0)
        for i, png in enumerate(png_list):
            svg_path = png_to_svg(png, mode_key)
            svg_files.append(svg_path)
            progress.progress((i + 1) / len(png_list))

        st.success("変換が完了しました！")

        # 個別ダウンロード
        for idx, svg in enumerate(svg_files):
            with open(svg, "rb") as f:
                st.download_button(
                    label=f"ページ {idx+1} をダウンロード（SVG）",
                    data=f,
                    file_name=f"page_{idx+1}.svg",
                    mime="image/svg+xml"
                )

        # ZIP まとめ
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

# =========================
# exe 内で Streamlit を起動
# =========================
if __name__ == "__main__":
    import time
    import webbrowser
    import sys

    # exe 内でのカレントディレクトリ調整
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Streamlit サーバー起動
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"]
    )

    time.sleep(2)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    import time
    import webbrowser
    import sys
    import os

    # exe 内でのカレントディレクトリ調整
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Streamlit がすでに起動しているか確認
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", 8501))
        s.close()
        # すでに起動している場合はブラウザだけ開く
        webbrowser.open("http://localhost:8501")
    except ConnectionRefusedError:
        # 起動していない場合はサーバーを立ち上げる
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"]
        )
        time.sleep(2)
        webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    import time
    import webbrowser
    import sys
    import os

    # exe 内でのカレントディレクトリ調整
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Streamlit がすでに起動しているか確認
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", 8501))
        s.close()
        # すでに起動している場合はブラウザだけ開く
        webbrowser.open("http://localhost:8501")
    except ConnectionRefusedError:
        # 起動していない場合はサーバーを立ち上げる
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"]
        )
        time.sleep(2)
        webbrowser.open("http://localhost:8501")

import os
import sys
import subprocess
import time
import webbrowser
import socket

def is_streamlit_running():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", 8501))
        s.close()
        return True
    except ConnectionRefusedError:
        return False

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Streamlit が起動していなければ起動
    if not is_streamlit_running():
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__), "--server.port", "8501"]
        )
        time.sleep(2)

    # 必ずブラウザを開く
    webbrowser.open("http://localhost:8501")

import os
import subprocess
import sys

def run_streamlit():
    script_path = os.path.abspath(sys.argv[0])
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        script_path,
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    subprocess.Popen(cmd)

# PyInstaller の再実行を防ぐ
if getattr(sys, 'frozen', False):
    # exe のときだけブラウザを開く
    run_streamlit()
else:
    # Python 実行時は普通に Streamlit が動く
    import streamlit as st
    # ここに通常の Streamlit アプリのコードを書く

