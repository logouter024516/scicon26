from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
import os
import platform
import time
from urllib.parse import quote_plus

if platform.system().lower().startswith("win"):
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

try:
    import qrcode
except Exception:
    qrcode = None

from missingfind.camera_pipe import read_frame_once
from missingfind.capture import capture_once
from missingfind.config import Paths, SearchConfig, ensure_dirs
from missingfind.health import run_health_check
from missingfind.phone_bridge import PhoneBridge
from missingfind.search import MissingFindSearch
from missingfind.service import get_capture_state, start_capture, stop_capture
from missingfind.storage import JsonStore

try:
    if hasattr(cv2, "setLogLevel") and hasattr(cv2, "LOG_LEVEL_ERROR"):
        cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
except Exception:
    pass

st.set_page_config(page_title="MissingFind", layout="wide")

paths = Paths()
ensure_dirs(paths)
db = JsonStore(paths.db_file)


@st.cache_resource(show_spinner=False)
def get_search_engine(top_k: int = 5) -> MissingFindSearch:
    return MissingFindSearch(paths, SearchConfig(top_k=top_k))


@st.cache_resource(show_spinner=False)
def get_phone_bridge() -> PhoneBridge:
    bridge = PhoneBridge()
    bridge.start()
    return bridge


search: MissingFindSearch | None = None
search_init_error: str | None = None
try:
    search = get_search_engine(5)
except Exception as e:
    search_init_error = str(e)

AUTO_CAPTURE_SETTINGS: dict[str, int | float | str] = {
    "event_detector": "motion",
    "motion_threshold": 1200,
    "still_seconds": 3,
    "min_motion_frames": 3,
    "min_new_object_area": 1800,
    "cooldown_seconds": 5,
    "clip_prompt": "a person putting down an object on a table or floor",
    "clip_threshold": 0.26,
    "clip_sample_interval": 5,
    "save_seconds": 5,
}


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1240px; padding-top: 2.4rem;}
        .mf-title {margin: 0 0 0.3rem 0; font-size: 2.0rem; font-weight: 700;}
        .mf-sub {margin: 0; color: #6f6f74;}
        .mf-sep {height:1px; border:none; background:#c9c9ce; margin:0.9rem 0 1.0rem 0;}
        .mf-card {
            background: white;
            border-radius: 22px;
            padding: 14px 16px;
            box-shadow: 0 14px 40px rgba(0,0,0,0.10);
        }
        .mf-footer {margin-top: 1.2rem; color:#80808a; text-align:center;}
        div[data-testid="stTabs"] [role="tablist"] {
            display:inline-flex; gap:8px; padding:6px; border-radius:999px;
            background:#f5f5f8; margin-bottom: 0.8rem;
        }
        div[data-testid="stTabs"] [role="tab"] {
            height:36px; border-radius:999px; padding:0 14px;
        }
        div[data-testid="stTabs"] [aria-selected="true"] {
            background:#ffffff; color:#0A84FF; font-weight:700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _greeting_text() -> str:
    h = datetime.now().hour
    if h < 12:
        period = "morning"
    elif h < 18:
        period = "afternoon"
    else:
        period = "evening"
    return f"Good {period},"


def _header(subtitle: str) -> None:
    st.markdown(f"<h1 class='mf-title'>{_greeting_text()}<br>{subtitle}</h1>", unsafe_allow_html=True)
    st.markdown("<p class='mf-sub'>All processing is local (edge). No video is uploaded to cloud.</p>", unsafe_allow_html=True)
    st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)


def _footer() -> None:
    st.markdown("<div class='mf-footer'>made with 💖 by DEVLOG</div>", unsafe_allow_html=True)


def _summary_card(title: str, value: str, desc: str) -> None:
    st.markdown(
        f"""
        <div class='mf-card'>
            <h4 style='margin:0'>{title}</h4>
            <hr style='border:none;height:1px;background:#dadbe2;margin:8px 0 10px 0'/>
            <div style='font-size:1.8rem;font-weight:700'>{value}</div>
            <div style='color:#6f6f74'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _read_image_bytes_safe(path: Path, retries: int = 4, delay: float = 0.04) -> bytes | None:
    if not path.exists():
        return None
    for _ in range(max(1, retries)):
        try:
            raw = path.read_bytes()
            if len(raw) < 128:
                time.sleep(delay)
                continue
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None and img.size > 0:
                return raw
        except Exception:
            pass
        time.sleep(delay)
    return None


def _render_preview(path: Path) -> bool:
    raw = _read_image_bytes_safe(path)
    if raw is None:
        return False
    b64 = base64.b64encode(raw).decode("ascii")
    st.markdown(
        f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;border-radius:14px;" alt="capture-preview"/>',
        unsafe_allow_html=True,
    )
    return True


def _read_frame_with_retries(index: int, backend_mode: str = "Auto") -> tuple[bool, np.ndarray | None]:
    ok, frame, _ = read_frame_once(index=index, backend_mode=backend_mode, retries=12, delay=0.05, width=1280, height=720)
    return ok, frame


def _render_qr(url: str) -> None:
    if qrcode is not None:
        img = qrcode.make(url)
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="Scan with phone", width=220)
    else:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={quote_plus(url)}"
        st.image(qr_url, caption="Scan with phone", width=220)


def _collect_crops(files: list, key_prefix: str) -> list[np.ndarray]:
    crops: list[np.ndarray] = []
    for i, f in enumerate(files):
        image = Image.open(BytesIO(f.getvalue())).convert("RGB")
        with st.expander(f"{f.name}", expanded=(i == 0)):
            cropped = st_cropper(
                image,
                realtime_update=True,
                box_color="#00FF66",
                aspect_ratio=None,
                return_type="image",
                key=f"{key_prefix}_cropper_{i}",
            )
            arr = np.array(cropped)
            st.image(arr, caption="ROI", width="stretch")
            crops.append(arr)
    return crops


_apply_theme()

if "live_last_result" not in st.session_state:
    st.session_state["live_last_result"] = None
if "live_has_result" not in st.session_state:
    st.session_state["live_has_result"] = False
if "phone_public_url" not in st.session_state:
    st.session_state["phone_public_url"] = None


tab_home, tab_capture, tab_live, tab_quick, tab_register, tab_logs, tab_health = st.tabs(
    ["Home", "Capture", "Live Search", "Quick Search", "Register", "Logs", "Health"]
)

with tab_home:
    _header("How can I assist you?")

    state = get_capture_state(paths)
    clips = db.clips()
    reg_count = len(search.list_registered_items()) if search is not None else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        _summary_card("Capture Status", "Running" if state.running else "Stopped", f"camera={state.camera_index if state.camera_index is not None else '-'}")
    with c2:
        _summary_card("Total Clips", str(len(clips)), "saved local clips")
    with c3:
        _summary_card("Added Items", str(reg_count), "few-shot registered items")

    st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)
    st.subheader("Summary")
    st.subheader("Recent clips")
    recent = list(reversed(clips[-10:]))
    if not recent:
        st.info("No clips yet.")
    else:
        for rec in recent:
            st.write(f"- {rec.get('clip_id')} | {rec.get('event_at')} | {rec.get('camera_id')}")

    if search_init_error:
        st.error(f"Search model initialization failed: {search_init_error}")

    _footer()

with tab_capture:
    _header("I’m monitoring your camera...")

    camera_index = st.number_input("Camera index", min_value=0, max_value=10, value=0, step=1)
    state = get_capture_state(paths)
    st.write(f"Status: {'Running' if state.running else 'Stopped'}")
    if state.running:
        st.caption(f"PID={state.pid} / camera={state.camera_index}")

    c1, c2, c3 = st.columns(3)
    if c1.button("Start Capture", type="primary", width="stretch"):
        try:
            started = start_capture(
                paths,
                int(camera_index),
                event_detector=str(AUTO_CAPTURE_SETTINGS["event_detector"]),
                motion_threshold=int(AUTO_CAPTURE_SETTINGS["motion_threshold"]),
                still_seconds=int(AUTO_CAPTURE_SETTINGS["still_seconds"]),
                min_motion_frames=int(AUTO_CAPTURE_SETTINGS["min_motion_frames"]),
                min_new_object_area=int(AUTO_CAPTURE_SETTINGS["min_new_object_area"]),
                cooldown_seconds=int(AUTO_CAPTURE_SETTINGS["cooldown_seconds"]),
                clip_prompt=str(AUTO_CAPTURE_SETTINGS["clip_prompt"]),
                clip_threshold=float(AUTO_CAPTURE_SETTINGS["clip_threshold"]),
                clip_sample_interval=int(AUTO_CAPTURE_SETTINGS["clip_sample_interval"]),
                save_seconds=int(AUTO_CAPTURE_SETTINGS["save_seconds"]),
            )
            st.success(f"Started: pid={started.pid}")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    if c2.button("Stop Capture", width="stretch"):
        stop_capture(paths)
        st.warning("Capture stopped.")
        st.rerun()

    if c3.button("Save Test Clip", width="stretch"):
        try:
            out = capture_once(paths, camera_index=int(camera_index), seconds=10, fps=20)
            st.success(f"Saved: {out}")
        except Exception as e:
            st.error(str(e))

    st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)
    st.subheader("Capture Preview")

    state = get_capture_state(paths)
    if state.running and st_autorefresh is not None:
        st_autorefresh(interval=350, limit=None, key="capture_preview_refresh")

    if paths.preview_file.exists():
        if not _render_preview(paths.preview_file):
            st.info("Preview is updating...")
        else:
            try:
                mtime = paths.preview_file.stat().st_mtime
                st.caption(f"Last update: {time.strftime('%H:%M:%S', time.localtime(mtime))}")
            except Exception:
                pass
    else:
        st.info("Preview appears after Capture starts.")

    _footer()

with tab_live:
    _header("I’ll find your item...")

    if search is None:
        st.error("Search model is not initialized.")
        _footer()
        st.stop()

    c_live_mode_1, c_live_mode_2 = st.columns([1, 2.2])
    with c_live_mode_1:
        st.subheader("Live Search")
    with c_live_mode_2:
        live_mode = st.radio("", ["Non added", "added"], horizontal=True, label_visibility="collapsed")
    use_registry = live_mode == "added"

    st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)

    if use_registry:
        items = search.list_registered_items()
        if items:
            query = st.selectbox("Registered item", options=items)
        else:
            query = ""
            st.warning("No registered items. Use Register tab first.")
    else:
        query = st.text_input("What are you looking for?", placeholder="e.g. black wallet")

    source = st.radio("Camera source", ["Smartphone (QR)", "PC Camera"], horizontal=True)

    frame_bgr: np.ndarray | None = None
    if source == "Smartphone (QR)":
        try:
            bridge = get_phone_bridge()
            public_auto = st.checkbox("Auto public HTTPS (Cloudflare)", value=False)
            public_url = None
            if public_auto:
                with st.spinner("Preparing HTTPS URL..."):
                    public_url = bridge.ensure_public_url(timeout_sec=3.0)
                if public_url:
                    st.session_state["phone_public_url"] = public_url
                else:
                    public_url = st.session_state.get("phone_public_url")
            status = bridge.build_status(access_base_url=public_url, sender_page="index.html")

            c_url, c_qr = st.columns([2.1, 1])
            with c_url:
                st.code(status.sender_url)
                st.caption(f"Frame API: {status.api_url}")
            with c_qr:
                _render_qr(status.sender_url)

            auto_live = st.checkbox("Auto analyze", value=True)
            refresh_ms = st.slider("Refresh(ms)", min_value=300, max_value=2500, value=900, step=100)
            if auto_live and st_autorefresh is not None:
                st_autorefresh(interval=int(refresh_ms), limit=None, key="live_auto_refresh")

            fr, ts = bridge.get_latest_frame()
            if fr is not None:
                frame_bgr = fr
                st.image(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), caption="Phone frame", width="stretch")
                if ts is not None:
                    st.caption(f"Last phone frame: {time.strftime('%H:%M:%S', time.localtime(ts))}")
            else:
                st.info("Open sender on phone and tap Start Streaming.")
        except Exception as e:
            st.error(str(e))
    else:
        cam_idx = st.number_input("PC webcam index", min_value=0, max_value=10, value=0, step=1)
        backend_mode = st.selectbox("Webcam backend", ["Auto", "DSHOW", "MSMF", "ANY"], index=0)
        use_capture_preview = st.checkbox("Use Capture preview (recommended for concurrent run)", value=True)

        cap_state = get_capture_state(paths)
        if use_capture_preview and cap_state.running and paths.preview_file.exists():
            raw = _read_image_bytes_safe(paths.preview_file)
            fr = None
            if raw is not None:
                arr = np.frombuffer(raw, dtype=np.uint8)
                fr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if fr is not None and fr.size > 0:
                frame_bgr = fr
                st.image(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), caption="Shared frame from Capture", width="stretch")
                st.caption("Capture + Live running concurrently using shared frame.")
            else:
                st.warning("Waiting for capture preview frame...")
        else:
            ok, fr = _read_frame_with_retries(int(cam_idx), backend_mode=backend_mode)
            if ok and fr is not None:
                frame_bgr = fr
                st.image(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), caption="PC camera frame", width="stretch")
            else:
                if cap_state.running:
                    st.warning("Capture may be locking this webcam. Enable 'Use Capture preview' or use another camera index.")
                else:
                    st.warning("Cannot read webcam frame.")

    run_now = st.button("Run Live Search", type="primary")
    if run_now:
        if not query.strip():
            st.warning("Enter/select item first.")
        elif frame_bgr is None:
            st.warning("Capture a frame first.")
        else:
            try:
                res = search.search_image(frame_bgr, query.strip(), use_registry=use_registry)
                st.session_state["live_last_result"] = {
                    "query": query.strip(),
                    "mode": live_mode,
                    "score": float(res.score),
                    "found": bool(res.found),
                    "message": str(res.message),
                    "image": cv2.cvtColor(res.image_bgr, cv2.COLOR_BGR2RGB),
                }
                st.session_state["live_has_result"] = True
            except Exception as e:
                st.error(str(e))

    if st.session_state.get("live_has_result") and isinstance(st.session_state.get("live_last_result"), dict):
        lr = st.session_state["live_last_result"]
        st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)
        st.subheader("Search result")
        c1, c2 = st.columns([1.3, 1.2])
        with c1:
            st.image(lr["image"], caption="preview image", width="stretch")
        with c2:
            st.write(f"- query: {lr['query']}")
            st.write(f"- mode: {lr['mode']}")
            st.write(f"- score: {lr['score']:.3f}")
            st.write(f"- status: {'found' if lr['found'] else 'not-found'}")
            st.write(f"- detail: {lr['message']}")

    _footer()

with tab_quick:
    _header("I’ll trace your item history...")

    if search is None:
        st.error("Search model is not initialized.")
        _footer()
        st.stop()

    mode = st.radio("Mode", ["미등록(Zero-shot)", "사전 등록(Few-shot)"], horizontal=True)
    use_registry = mode == "사전 등록(Few-shot)"

    if use_registry:
        items = search.list_registered_items()
        if items:
            query = st.selectbox("Registered item", options=items, key="quick_query_registered")
        else:
            query = ""
            st.warning("No registered items. Use Register tab first.")
    else:
        query = st.text_input("Find item", placeholder="예: 검은 지갑", key="quick_query_text")

    top_k = st.slider("Results", min_value=1, max_value=10, value=5)

    if st.button("Run Quick Search", type="primary"):
        if not query.strip():
            st.warning("Enter/select item first.")
        else:
            try:
                search.cfg.top_k = int(top_k)
                hits = search.quick_search(query.strip(), use_registry=use_registry)
            except Exception as e:
                st.error(str(e))
                hits = []

            if not hits:
                st.info("No results")
            else:
                st.subheader("Search result")
                for h in hits:
                    w1, w2 = st.columns([1, 2])
                    with w1:
                        st.image(h.thumbnail_path, caption=f"{h.clip_id} / {h.score:.3f}")
                    with w2:
                        st.write(f"- clip: {h.clip_path}")
                        st.write(f"- t: {h.time_sec:.1f}s")
                        st.write(f"- object/action: {h.object_score:.3f} / {h.action_score:.3f}")
                        if Path(h.clip_path).exists():
                            st.video(h.clip_path, start_time=max(0, int(h.time_sec) - 2))

    _footer()

with tab_register:
    _header("I’ll add your item...")

    if search is None:
        st.error("Search model is not initialized.")
        _footer()
        st.stop()

    st.subheader("Upload and register")
    name = st.text_input("Item name", placeholder="e.g. my key")
    files = st.file_uploader("Images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    if st.button("Register item", type="primary"):
        if not name.strip():
            st.warning("Enter item name.")
        elif not files:
            st.warning("Upload at least one image.")
        else:
            crops = _collect_crops(files, key_prefix=f"reg_{name.strip()}")
            temp_dir = paths.base_dir / "_uploads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: list[Path] = []
            for i, arr in enumerate(crops):
                out = temp_dir / f"{name.strip()}_{i}.jpg"
                cv2.imwrite(str(out), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
                saved_paths.append(out)
            try:
                search.register_from_images(name.strip(), saved_paths)
                st.success(f"Registered: {name.strip()}")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.markdown('<hr class="mf-sep"/>', unsafe_allow_html=True)
    st.subheader("Manage items")
    items = search.list_registered_items()
    if not items:
        st.info("No registered items")
    else:
        selected = st.selectbox("Item", options=items)
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Rename to", placeholder="new name")
            if st.button("Rename"):
                try:
                    search.rename_registered_item(selected, new_name.strip())
                    st.success("Renamed")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with c2:
            if st.button("Delete", type="secondary"):
                try:
                    search.delete_registered_item(selected)
                    st.warning("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    _footer()

with tab_logs:
    _header("I’ll show recent capture logs...")
    if paths.log_file.exists():
        txt = paths.log_file.read_text(encoding="utf-8", errors="ignore")
        st.text_area("capture.log", txt[-20000:], height=420)
    else:
        st.info("No logs yet.")
    if st.button("Refresh Logs"):
        st.rerun()
    _footer()

with tab_health:
    _header("I’ll check system health...")
    cam = st.number_input("Camera index", min_value=0, max_value=10, value=0, step=1, key="health_cam")
    include_models = st.checkbox("Include model loading test", value=False)
    if st.button("Run Health Check", type="primary"):
        checks = run_health_check(paths, camera_index=int(cam), include_models=include_models)
        failed = False
        for c in checks:
            if c.ok:
                st.success(f"{c.name}: {c.detail}")
            else:
                st.error(f"{c.name}: {c.detail}")
                failed = True
        if not failed:
            st.info("All checks passed")
    _footer()
