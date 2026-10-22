"""Modern Desktop GUI Application for Face Recognition Assistant.

Built with Tkinter (native Python on Windows) with real-time video rendering,
live enrollment, image recognition, datastore management, and web dashboard integration.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import (
    Button,
    Canvas,
    Checkbutton,
    DoubleVar,
    Entry,
    Frame,
    IntVar,
    Label,
    Listbox,
    Menu,
    PhotoImage,
    Scale,
    Scrollbar,
    StringVar,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    ttk,
)
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from core_engine import FaceEngine, FaceMatchResult

# Dark theme palette
BG_DARK = "#121214"
BG_CARD = "#1a1a22"
BG_CARD_LIGHTER = "#22232e"
BORDER_COLOR = "#2e303e"
ACCENT = "#6366f1"
ACCENT_HOVER = "#4f46e5"
SUCCESS = "#10b981"
DANGER = "#ef4444"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#94a3b8"


class FaceRecognitionApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("OwnerAI - Unified Face Recognition Studio")
        self.root.geometry("1100x740")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG_DARK)

        # Engine
        self.engine = FaceEngine(model_name="facenet")

        # Camera state
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_running = False
        self.camera_thread: Optional[threading.Thread] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_results: List[FaceMatchResult] = []
        self.current_fps = 0.0

        # Server process handle
        self.server_process: Optional[subprocess.Popen] = None

        self._photo_cache: Optional[PhotoImage] = None
        self._static_photo_cache: Optional[PhotoImage] = None

        self._setup_styles()
        self._build_ui()
        self.refresh_database_view()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BG_DARK, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG_CARD,
            foreground=TEXT_MUTED,
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#ffffff")],
        )

        style.configure("Treeview", background=BG_CARD, fieldbackground=BG_CARD, foreground=TEXT_MAIN, borderwidth=0)
        style.configure("Treeview.Heading", background=BG_CARD_LIGHTER, foreground=TEXT_MAIN, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])

    def _build_ui(self) -> None:
        # Header banner
        header = Frame(self.root, bg=BG_CARD, height=64, padx=20, pady=12)
        header.pack(fill="x", side="top")

        title_lbl = Label(
            header,
            text="OwnerAI Face Recognition Studio",
            font=("Segoe UI", 15, "bold"),
            bg=BG_CARD,
            fg=TEXT_MAIN,
        )
        title_lbl.pack(side="left")

        # Model selector dropdown
        model_frame = Frame(header, bg=BG_CARD)
        model_frame.pack(side="right")

        Label(model_frame, text="Model:", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.model_var = StringVar(value="facenet")
        model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=["facenet", "mobile_facenet"],
            state="readonly",
            width=14,
        )
        model_combo.pack(side="left")
        model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        self.identities_badge = Label(
            header,
            text="Enrolled: 0",
            bg="#27273a",
            fg=SUCCESS,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
        )
        self.identities_badge.pack(side="right", padx=16)

        # Tab Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=12)

        # Tabs
        self.tab_live = Frame(self.notebook, bg=BG_DARK)
        self.tab_static = Frame(self.notebook, bg=BG_DARK)
        self.tab_enroll = Frame(self.notebook, bg=BG_DARK)
        self.tab_database = Frame(self.notebook, bg=BG_DARK)
        self.tab_web = Frame(self.notebook, bg=BG_DARK)

        self.notebook.add(self.tab_live, text="  Live Recognition  ")
        self.notebook.add(self.tab_static, text="  Image Analysis  ")
        self.notebook.add(self.tab_enroll, text="  Enroll Identity  ")
        self.notebook.add(self.tab_database, text="  Identity Database  ")
        self.notebook.add(self.tab_web, text="  Web Dashboard  ")

        self._build_live_tab()
        self._build_static_tab()
        self._build_enroll_tab()
        self._build_database_tab()
        self._build_web_tab()

    # -------------------------------------------------------------------------
    # Tab 1: Live Recognition
    # -------------------------------------------------------------------------
    def _build_live_tab(self) -> None:
        container = Frame(self.tab_live, bg=BG_DARK)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # Video Canvas
        left_col = Frame(container, bg=BG_CARD, padx=8, pady=8)
        left_col.pack(side="left", fill="both", expand=True)

        self.video_canvas = Canvas(left_col, bg="#0d0d10", highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.video_canvas.pack(fill="both", expand=True)

        # Right Controls Panel
        right_col = Frame(container, bg=BG_CARD, width=300, padx=16, pady=16)
        right_col.pack(side="right", fill="y", padx=(12, 0))
        right_col.pack_propagate(False)

        Label(right_col, text="Camera Controls", font=("Segoe UI", 12, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(0, 12))

        self.btn_toggle_cam = Button(
            right_col,
            text="Start Webcam",
            command=self.toggle_camera,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_HOVER,
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        )
        self.btn_toggle_cam.pack(fill="x", pady=6)

        self.btn_enroll_live_face = Button(
            right_col,
            text="Enroll Detected Face",
            command=self._enroll_current_live_face,
            bg=SUCCESS,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        )
        self.btn_enroll_live_face.pack(fill="x", pady=6)

        # Threshold slider
        Label(right_col, text="Recognition Threshold", font=("Segoe UI", 9, "bold"), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(18, 4))
        self.threshold_var = DoubleVar(value=float(self.engine.config.get("recognition_threshold", 0.1)))
        self.threshold_slider = Scale(
            right_col,
            from_=0.05,
            to=0.95,
            resolution=0.05,
            orient="horizontal",
            variable=self.threshold_var,
            bg=BG_CARD,
            fg=TEXT_MAIN,
            troughcolor=BG_CARD_LIGHTER,
            highlightthickness=0,
        )
        self.threshold_slider.pack(fill="x")

        # Stats
        Label(right_col, text="Live Feed Stats", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(24, 6))
        self.lbl_live_status = Label(right_col, text="Camera stopped", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9))
        self.lbl_live_status.pack(anchor="w")

        self.lbl_live_faces = Label(right_col, text="Faces detected: 0", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9))
        self.lbl_live_faces.pack(anchor="w")

        self.lbl_live_match = Label(right_col, text="Matches: None", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9))
        self.lbl_live_match.pack(anchor="w")

    def toggle_camera(self) -> None:
        if self.is_camera_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self) -> None:
        if self.is_camera_running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap or not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Could not open video capture device (Camera Index 0).")
            return

        self.is_camera_running = True
        self.btn_toggle_cam.configure(text="Stop Webcam", bg=DANGER)
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()

    def stop_camera(self) -> None:
        self.is_camera_running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.btn_toggle_cam.configure(text="Start Webcam", bg=ACCENT)
        self.lbl_live_status.configure(text="Camera stopped", fg=TEXT_MUTED)

    def _camera_loop(self) -> None:
        prev_time = time.time()
        datastore = self.engine.load_datastore()

        while self.is_camera_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            now = time.time()
            fps = 1.0 / max(now - prev_time, 0.001)
            prev_time = now
            self.current_fps = fps

            # Recognize
            thresh = float(self.threshold_var.get())
            results = self.engine.process_frame(frame, threshold=thresh, datastore=datastore)
            self.latest_frame = frame
            self.latest_results = results

            annotated = self.engine.draw_results(frame, results, fps=fps)

            # Render to Tkinter
            self._render_frame_to_canvas(annotated)

            # Update stats
            matches_text = ", ".join([f"{r.name} ({r.confidence*100:.0f}%)" for r in results if r.is_known]) or "None"
            self.root.after(0, self._update_live_labels, len(results), matches_text, fps)

            time.sleep(0.015)

    def _update_live_labels(self, face_count: int, matches_str: str, fps: float) -> None:
        self.lbl_live_status.configure(text=f"Live ({fps:.1f} FPS)", fg=SUCCESS)
        self.lbl_live_faces.configure(text=f"Faces detected: {face_count}")
        self.lbl_live_match.configure(text=f"Matches: {matches_str}", fg=SUCCESS if matches_str != "None" else TEXT_MUTED)

    def _render_frame_to_canvas(self, bgr_frame: np.ndarray) -> None:
        canvas_w = self.video_canvas.winfo_width()
        canvas_h = self.video_canvas.winfo_height()
        if canvas_w < 50 or canvas_h < 50:
            return

        h, w = bgr_frame.shape[:2]
        ratio = min(canvas_w / w, canvas_h / h)
        new_w, new_h = max(1, int(w * ratio)), max(1, int(h * ratio))

        resized = cv2.resize(bgr_frame, (new_w, new_h))
        ok, buf = cv2.imencode(".png", resized)
        if not ok:
            return

        b64 = base64.b64encode(buf).decode("ascii")
        try:
            self.root.after(0, self._set_canvas_image, b64, canvas_w, canvas_h, new_w, new_h)
        except Exception:
            pass

    def _set_canvas_image(self, b64_png: str, cw: int, ch: int, nw: int, nh: int) -> None:
        self._photo_cache = PhotoImage(data=b64_png)
        self.video_canvas.delete("all")
        self.video_canvas.create_image(cw // 2, ch // 2, image=self._photo_cache)

    def _enroll_current_live_face(self) -> None:
        if self.latest_frame is None or not self.latest_results:
            messagebox.showwarning("No Face", "No face is currently detected in the camera feed.")
            return

        # Prompt for name
        dialog = Toplevel(self.root)
        dialog.title("Enroll Detected Face")
        dialog.geometry("380x180")
        dialog.configure(bg=BG_CARD)
        dialog.grab_set()

        Label(dialog, text="Enter Identity Name:", bg=BG_CARD, fg=TEXT_MAIN, font=("Segoe UI", 11, "bold")).pack(pady=(20, 8))
        entry = Entry(dialog, font=("Segoe UI", 11), bg=BG_CARD_LIGHTER, fg=TEXT_MAIN, insertbackground="white")
        entry.pack(fill="x", padx=30, pady=4)
        entry.focus_set()

        def submit():
            name = entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name cannot be empty.", parent=dialog)
                return

            dialog.destroy()
            frame_copy = self.latest_frame.copy()
            ok, final_name, msg = self.engine.enroll_from_image(frame_copy, name)
            if ok:
                messagebox.showinfo("Success", msg)
                self.refresh_database_view()
            else:
                messagebox.showerror("Enrollment Failed", msg)

        Button(dialog, text="Save Face", command=submit, bg=SUCCESS, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=6).pack(pady=16)

    # -------------------------------------------------------------------------
    # Tab 2: Static Image Analysis
    # -------------------------------------------------------------------------
    def _build_static_tab(self) -> None:
        top_bar = Frame(self.tab_static, bg=BG_CARD, padx=16, pady=10)
        top_bar.pack(fill="x", side="top", padx=8, pady=8)

        Button(
            top_bar,
            text="Choose Image File...",
            command=self._select_and_analyze_image,
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side="left")

        self.lbl_static_file = Label(top_bar, text="No image selected", bg=BG_CARD, fg=TEXT_MUTED)
        self.lbl_static_file.pack(side="left", padx=14)

        # Split pane
        split = Frame(self.tab_static, bg=BG_DARK)
        split.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Image canvas
        img_col = Frame(split, bg=BG_CARD, padx=8, pady=8)
        img_col.pack(side="left", fill="both", expand=True)

        self.static_canvas = Canvas(img_col, bg="#0d0d10", highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.static_canvas.pack(fill="both", expand=True)

        # Results table
        table_col = Frame(split, bg=BG_CARD, width=320, padx=12, pady=12)
        table_col.pack(side="right", fill="y", padx=(10, 0))
        table_col.pack_propagate(False)

        Label(table_col, text="Detection Results", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(0, 8))

        self.static_tree = ttk.Treeview(table_col, columns=("Name", "Confidence"), show="headings", height=15)
        self.static_tree.heading("Name", text="Identity")
        self.static_tree.heading("Confidence", text="Score")
        self.static_tree.column("Name", width=160)
        self.static_tree.column("Confidence", width=100)
        self.static_tree.pack(fill="both", expand=True)

    def _select_and_analyze_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Image for Face Recognition",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All Files", "*.*")],
        )
        if not path:
            return

        self.lbl_static_file.configure(text=Path(path).name, fg=TEXT_MAIN)
        thresh = float(self.threshold_var.get())
        results, annotated, msg = self.engine.recognize_image_file(path, threshold=thresh)

        if annotated is None:
            messagebox.showerror("Analysis Error", msg)
            return

        # Clear tree
        for row in self.static_tree.get_children():
            self.static_tree.delete(row)

        for r in results:
            self.static_tree.insert("", "end", values=(r.name, f"{r.confidence*100:.1f}%"))

        # Render image
        self._render_static_image(annotated)

    def _render_static_image(self, bgr_img: np.ndarray) -> None:
        canvas_w = self.static_canvas.winfo_width() or 600
        canvas_h = self.static_canvas.winfo_height() or 500
        h, w = bgr_img.shape[:2]
        ratio = min(canvas_w / w, canvas_h / h)
        nw, nh = max(1, int(w * ratio)), max(1, int(h * ratio))

        resized = cv2.resize(bgr_img, (nw, nh))
        ok, buf = cv2.imencode(".png", resized)
        if ok:
            b64 = base64.b64encode(buf).decode("ascii")
            self._static_photo_cache = PhotoImage(data=b64)
            self.static_canvas.delete("all")
            self.static_canvas.create_image(canvas_w // 2, canvas_h // 2, image=self._static_photo_cache)

    # -------------------------------------------------------------------------
    # Tab 3: Enroll Identity
    # -------------------------------------------------------------------------
    def _build_enroll_tab(self) -> None:
        card = Frame(self.tab_enroll, bg=BG_CARD, padx=28, pady=24)
        card.pack(fill="both", expand=True, padx=40, pady=20)

        Label(card, text="Add New Face Identity", font=("Segoe UI", 14, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(0, 16))

        # Identity Name input
        Label(card, text="Full Name / Label:", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(4, 2))
        self.enroll_name_entry = Entry(card, font=("Segoe UI", 11), bg=BG_CARD_LIGHTER, fg=TEXT_MAIN, insertbackground="white", width=40)
        self.enroll_name_entry.pack(anchor="w", pady=(0, 16))

        # Method 1: Single Image File
        Label(card, text="Option 1: Enroll from Single Image File", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(12, 6))
        Button(
            card,
            text="Choose Image and Enroll",
            command=self._enroll_from_file_dialog,
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(anchor="w", pady=(0, 16))

        # Method 2: Multi-image averaging
        Label(card, text="Option 2: Multi-Angle Accurate Enrollment (Average Embeddings)", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(12, 6))
        Label(
            card,
            text="Select 2 to 5 different pictures of the same person. Their embeddings will be averaged for robust accuracy.",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 8))
        Button(
            card,
            text="Select Multiple Images and Enroll",
            command=self._enroll_from_multiple_files_dialog,
            bg=SUCCESS,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(anchor="w", pady=(0, 16))

    def _enroll_from_file_dialog(self) -> None:
        name = self.enroll_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a Name or Label above before selecting an image.")
            return

        path = filedialog.askopenfilename(
            title="Select Face Image to Enroll",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")],
        )
        if not path:
            return

        ok, enrolled_name, msg = self.engine.enroll_from_image(path, name)
        if ok:
            messagebox.showinfo("Enrollment Succeeded", msg)
            self.enroll_name_entry.delete(0, "end")
            self.refresh_database_view()
        else:
            messagebox.showerror("Enrollment Failed", msg)

    def _enroll_from_multiple_files_dialog(self) -> None:
        name = self.enroll_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a Name or Label above before selecting images.")
            return

        paths = filedialog.askopenfilenames(
            title="Select Multiple Face Images to Average and Enroll",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")],
        )
        if not paths:
            return

        ok, enrolled_name, msg = self.engine.enroll_from_multiple_images(list(paths), name)
        if ok:
            messagebox.showinfo("Enrollment Succeeded", msg)
            self.enroll_name_entry.delete(0, "end")
            self.refresh_database_view()
        else:
            messagebox.showerror("Enrollment Failed", msg)

    # -------------------------------------------------------------------------
    # Tab 4: Database Manager
    # -------------------------------------------------------------------------
    def _build_database_tab(self) -> None:
        container = Frame(self.tab_database, bg=BG_DARK, padx=16, pady=12)
        container.pack(fill="both", expand=True)

        toolbar = Frame(container, bg=BG_CARD, padx=12, pady=10)
        toolbar.pack(fill="x", side="top", pady=(0, 10))

        Button(toolbar, text="Refresh Database", command=self.refresh_database_view, bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5).pack(side="left")
        Button(toolbar, text="Delete Selected Identity", command=self._delete_selected_identity, bg=DANGER, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5).pack(side="left", padx=10)

        # Search
        Label(toolbar, text="Search:", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(20, 6))
        self.db_search_var = StringVar()
        self.db_search_var.trace_add("write", lambda *_: self._filter_database_view())
        Entry(toolbar, textvariable=self.db_search_var, bg=BG_CARD_LIGHTER, fg=TEXT_MAIN, insertbackground="white", width=20).pack(side="left")

        # Treeview
        self.db_tree = ttk.Treeview(container, columns=("Name", "Dimensions", "Datastore Path"), show="headings", height=18)
        self.db_tree.heading("Name", text="Identity Name")
        self.db_tree.heading("Dimensions", text="Vector Dimension")
        self.db_tree.heading("Datastore Path", text="Storage Location")

        self.db_tree.column("Name", width=220)
        self.db_tree.column("Dimensions", width=140)
        self.db_tree.column("Datastore Path", width=420)
        self.db_tree.pack(fill="both", expand=True)

    def refresh_database_view(self) -> None:
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)

        identities = self.engine.list_identities()
        datastore_name = self.engine.get_datastore_path().as_posix()

        for ident in identities:
            self.db_tree.insert(
                "",
                "end",
                values=(ident["name"], f"{ident['dimension']}-Dim", datastore_name),
            )

        self.identities_badge.configure(text=f"Enrolled: {len(identities)}")

    def _filter_database_view(self) -> None:
        query = self.db_search_var.get().strip().lower()
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)

        identities = self.engine.list_identities()
        datastore_name = self.engine.get_datastore_path().as_posix()

        for ident in identities:
            if not query or query in ident["name"].lower():
                self.db_tree.insert(
                    "",
                    "end",
                    values=(ident["name"], f"{ident['dimension']}-Dim", datastore_name),
                )

    def _delete_selected_identity(self) -> None:
        selected = self.db_tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select an identity from the list to delete.")
            return

        values = self.db_tree.item(selected[0], "values")
        name = values[0]

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove identity '{name}' from the datastore?"):
            return

        ok, msg = self.engine.remove_identity(name)
        if ok:
            messagebox.showinfo("Removed", msg)
            self.refresh_database_view()
        else:
            messagebox.showerror("Error", msg)

    # -------------------------------------------------------------------------
    # Tab 5: Web Dashboard
    # -------------------------------------------------------------------------
    def _build_web_tab(self) -> None:
        card = Frame(self.tab_web, bg=BG_CARD, padx=28, pady=24)
        card.pack(fill="both", expand=True, padx=40, pady=20)

        Label(card, text="OwnerAI Web Dashboard Server", font=("Segoe UI", 14, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(anchor="w", pady=(0, 8))
        Label(
            card,
            text="The web backend provides consent-gated owner verification, device management, and secure encrypted biometrics.",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 20))

        status_box = Frame(card, bg=BG_CARD_LIGHTER, padx=16, pady=16)
        status_box.pack(fill="x", pady=(0, 20))

        Label(status_box, text="Server URL: http://127.0.0.1:8000", font=("Segoe UI", 11, "bold"), bg=BG_CARD_LIGHTER, fg=TEXT_MAIN).pack(anchor="w")
        Label(status_box, text="Default Port: 8000 | Bind: Localhost (127.0.0.1)", font=("Segoe UI", 9), bg=BG_CARD_LIGHTER, fg=TEXT_MUTED).pack(anchor="w", pady=(4, 0))

        actions = Frame(card, bg=BG_CARD)
        actions.pack(anchor="w", pady=10)

        Button(
            actions,
            text="Open Web Dashboard in Browser",
            command=lambda: webbrowser.open("http://127.0.0.1:8000"),
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(0, 12))

        Button(
            actions,
            text="Start/Restart Server (Port 8000)",
            command=self._launch_web_server_process,
            bg=SUCCESS,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side="left")

    def _launch_web_server_process(self) -> None:
        # Launch python app.py in background if not already running
        python_exe = sys.executable
        try:
            cmd = [python_exe, "app.py"]
            subprocess.Popen(cmd, cwd=os.getcwd())
            messagebox.showinfo("Server Started", "Web server launched on http://127.0.0.1:8000!\nOpening in browser...")
            webbrowser.open("http://127.0.0.1:8000")
        except Exception as exc:
            messagebox.showerror("Launch Error", f"Failed to start server: {exc}")

    # -------------------------------------------------------------------------
    # Switch Model
    # -------------------------------------------------------------------------
    def _on_model_change(self, event=None) -> None:
        model = self.model_var.get()
        try:
            self.engine.set_model(model)
            thresh = float(self.engine.config.get("recognition_threshold", 0.1))
            self.threshold_var.set(thresh)
            self.refresh_database_view()
            messagebox.showinfo("Model Switched", f"Active model set to '{model}' ({self.engine.config['output_size']}-Dim).")
        except Exception as exc:
            messagebox.showerror("Model Switch Error", str(exc))

    def on_closing(self) -> None:
        self.stop_camera()
        self.root.destroy()


def run_gui():
    root = Tk()
    app = FaceRecognitionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
