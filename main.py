"""Master Application Launcher.

Provides a unified interface for the entire project:
- Desktop GUI Studio (Tkinter)
- Live Camera Face Recognition
- Live Face Enrollment
- Static Image Recognition & Enrollment
- Datastore Management (List, Search, Remove)
- Web Application Server (OwnerAI FastAPI)
- Automated Test Suite Execution
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Suppress verbose oneDNN warning if not set
if "TF_ENABLE_ONEDNN_OPTS" not in os.environ:
    os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import cv2

from core_engine import FaceEngine


def cmd_gui() -> None:
    """Launch the modern desktop graphical studio."""
    from gui_app import run_gui

    print("Starting Desktop GUI Studio...")
    run_gui()


def cmd_live(model: str, threshold: float | None = None) -> None:
    """Run real-time webcam recognition."""
    engine = FaceEngine(model_name=model)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam (Camera index 0).")
        return

    print("\n=======================================================")
    print(f" LIVE FACE RECOGNITION - Model: {model.upper()}")
    print(f" Datastore: {engine.get_datastore_path().name} ({len(engine.load_datastore())} enrolled)")
    print(" Controls: Press 'q' to quit, 's' to snapshot & enroll")
    print("=======================================================\n")

    prev_time = time.time()
    datastore = engine.load_datastore()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[ERROR] Failed to read frame from webcam.")
                break

            now = time.time()
            fps = 1.0 / max(now - prev_time, 0.001)
            prev_time = now

            results = engine.process_frame(frame, threshold=threshold, datastore=datastore)
            annotated = engine.draw_results(frame, results, fps=fps)

            cv2.imshow("OwnerAI - Live Recognition (Press 'q' to quit, 's' to enroll)", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                name = input("\nEnter name for the detected face: ").strip()
                if name:
                    ok, final_name, msg = engine.enroll_from_image(frame, name)
                    print(f"-> {msg}")
                    if ok:
                        datastore = engine.load_datastore()
    finally:
        cap.release()
        cv2.destroyAllWindows()


def cmd_enroll_live(model: str) -> None:
    """Interactive webcam face enrollment."""
    engine = FaceEngine(model_name=model)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    print("\n=======================================================")
    print(f" LIVE FACE ENROLLMENT - Model: {model.upper()}")
    print(" Press 'c' to capture face & enter name | 'q' to quit")
    print("=======================================================\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            faces = engine.detect_faces(frame)
            display = frame.copy()
            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x + w, y + h), (46, 204, 113), 2)

            count_txt = f"Faces in view: {len(faces)} | Press 'c' to capture"
            cv2.putText(display, count_txt, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow("OwnerAI - Enroll Face (Press 'c' to capture, 'q' to quit)", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c"):
                if not faces:
                    print("[!] No face detected in frame. Please face the camera and try again.")
                    continue

                name = input("\nEnter name for the captured face: ").strip()
                if not name:
                    print("[!] Cancelled: name was empty.")
                    continue

                ok, final_name, msg = engine.enroll_from_image(frame, name)
                print(f"-> {msg}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


def cmd_recognize_image(image_path: str, model: str, threshold: float | None = None) -> None:
    """Analyze and recognize all faces in a static image."""
    engine = FaceEngine(model_name=model)
    results, annotated, msg = engine.recognize_image_file(image_path, threshold=threshold)
    if annotated is None:
        print(f"[ERROR] {msg}")
        return

    print(f"\n--- Recognition Results for: {image_path} ---")
    print(f"Total faces detected: {len(results)}")
    for i, r in enumerate(results, 1):
        status = "MATCH" if r.is_known else "UNKNOWN"
        print(f"  [{i}] {status} -> Name: {r.name} | Confidence: {r.confidence * 100:.2f}% | Box: {r.bbox}")

    # Display image
    cv2.imshow(f"Recognition: {Path(image_path).name} (Press any key to close)", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def cmd_enroll_image(image_path: str, name: str, model: str) -> None:
    """Enroll a face from an image file."""
    engine = FaceEngine(model_name=model)
    ok, final_name, msg = engine.enroll_from_image(image_path, name)
    print(f"\n-> {msg}")


def cmd_list_faces(model: str) -> None:
    """List all enrolled identities."""
    engine = FaceEngine(model_name=model)
    identities = engine.list_identities()
    path = engine.get_datastore_path()
    print(f"\n--- Enrolled Identities in {path.name} (Total: {len(identities)}) ---")
    for i, item in enumerate(identities, 1):
        print(f"  {i:3d}. {item['name']:<25} ({item['dimension']}-Dim)")


def cmd_remove_face(name: str, model: str) -> None:
    """Delete an identity from datastore."""
    engine = FaceEngine(model_name=model)
    ok, msg = engine.remove_identity(name)
    print(f"\n-> {msg}")


def cmd_web(port: int = 8000, modern: bool = True) -> None:
    """Launch the Full-Stack AI Surveillance Platform (Web Dashboard + APIs + AI Engine)."""
    os.environ["PORT"] = str(port)
    if modern:
        import webbrowser

        import uvicorn
        print("\n=======================================================")
        print(" FULL-STACK PRIVACY-FIRST AI SURVEILLANCE PLATFORM")
        print(f" Web Dashboard: http://127.0.0.1:{port}")
        print(f" API Docs:      http://127.0.0.1:{port}/docs")
        print(" Auth Mode:     Owner-Gated (Configure credentials via .env)")
        print("=======================================================\n")
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass
        uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=False)
    else:
        from app import main as start_web
        print(f"\nStarting Legacy OwnerAI Web on http://127.0.0.1:{port}...")
        start_web()


def cmd_test() -> None:
    """Run the automated test suite."""
    print("\nRunning automated integration tests via pytest...\n")
    subprocess.run([sys.executable, "-m", "pytest", "backend/tests", "-v"])


def interactive_menu() -> None:
    """Interactive console menu when no arguments are given."""
    while True:
        print("\n=======================================================")
        print("   AI Surveillance & Face Recognition Studio Menu       ")
        print("=======================================================")
        print("  1. Start Full-Stack AI Surveillance Web Platform [Recommended]")
        print("  2. Launch Desktop GUI Studio (Tkinter)")
        print("  3. Start Live Webcam Face Recognition (OpenCV HUD)")
        print("  4. Enroll New Face from Webcam")
        print("  5. Recognize Face in Image File")
        print("  6. Enroll Face from Image File")
        print("  7. List Enrolled Faces in Datastore")
        print("  8. Delete Face from Datastore")
        print("  9. Run Integration & Automated Test Suite")
        print("  0. Exit")
        print("=======================================================")
        choice = input("Select an option (0-9) [Default: 1]: ").strip() or "1"

        if choice == "1":
            cmd_web()
            break
        elif choice == "2":
            cmd_gui()
            break
        elif choice == "3":
            cmd_live(model="facenet")
        elif choice == "4":
            cmd_enroll_live(model="facenet")
        elif choice == "5":
            p = input("Enter image path: ").strip().strip('"')
            if p:
                cmd_recognize_image(p, model="facenet")
        elif choice == "6":
            p = input("Enter image path: ").strip().strip('"')
            n = input("Enter person name: ").strip()
            if p and n:
                cmd_enroll_image(p, n, model="facenet")
        elif choice == "7":
            cmd_list_faces(model="facenet")
        elif choice == "8":
            n = input("Enter identity name to remove: ").strip()
            if n:
                cmd_remove_face(n, model="facenet")
        elif choice == "9":
            cmd_test()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("[!] Invalid option. Please choose between 0 and 9.")


def main() -> None:
    parser = argparse.ArgumentParser(description="OwnerAI Face Recognition & Camera Assistant")
    subparsers = parser.add_subparsers(dest="command")

    # GUI
    subparsers.add_parser("gui", help="Launch the Desktop GUI Studio")

    # Live
    live_p = subparsers.add_parser("live", help="Run live webcam face recognition")
    live_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"], help="Model name")
    live_p.add_argument("--threshold", type=float, default=None, help="Recognition threshold")

    # Enroll live
    enr_live_p = subparsers.add_parser("enroll-live", help="Enroll face live using webcam")
    enr_live_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"])

    # Recognize image
    rec_img_p = subparsers.add_parser("recognize-image", help="Recognize face in a static image")
    rec_img_p.add_argument("--image", required=True, help="Path to image file")
    rec_img_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"])
    rec_img_p.add_argument("--threshold", type=float, default=None)

    # Enroll image
    enr_img_p = subparsers.add_parser("enroll-image", help="Enroll face from static image")
    enr_img_p.add_argument("--image", required=True, help="Path to image file")
    enr_img_p.add_argument("--name", required=True, help="Identity name")
    enr_img_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"])

    # List
    list_p = subparsers.add_parser("list-faces", help="List enrolled identities")
    list_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"])

    # Remove
    rem_p = subparsers.add_parser("remove-face", help="Remove an identity from datastore")
    rem_p.add_argument("--name", required=True, help="Identity name to remove")
    rem_p.add_argument("--model", default="facenet", choices=["facenet", "mobile_facenet"])

    # Web
    web_p = subparsers.add_parser("web", help="Start the FastAPI web dashboard")
    web_p.add_argument("--port", type=int, default=8000, help="Port to listen on")

    # Test
    subparsers.add_parser("test", help="Run automated test suite")

    # Doctor
    doctor_p = subparsers.add_parser(
        "doctor", help="Run startup health probes (camera, model, DB, disk)"
    )
    doctor_p.add_argument(
        "--benchmark",
        action="store_true",
        help="Also benchmark the AI provider latency",
    )

    args = parser.parse_args()

    if not args.command:
        # If no arguments provided in CLI, launch interactive menu
        interactive_menu()
    elif args.command == "gui":
        cmd_gui()
    elif args.command == "live":
        cmd_live(model=args.model, threshold=args.threshold)
    elif args.command == "enroll-live":
        cmd_enroll_live(model=args.model)
    elif args.command == "recognize-image":
        cmd_recognize_image(args.image, model=args.model, threshold=args.threshold)
    elif args.command == "enroll-image":
        cmd_enroll_image(args.image, args.name, model=args.model)
    elif args.command == "list-faces":
        cmd_list_faces(model=args.model)
    elif args.command == "remove-face":
        cmd_remove_face(args.name, model=args.model)
    elif args.command == "web":
        cmd_web(port=args.port)
    elif args.command == "test":
        cmd_test()
    elif args.command == "doctor":
        cmd_doctor()
        if getattr(args, "benchmark", False):
            cmd_doctor_benchmark()


# ---------------------------------------------------------------------------
# Doctor command (OpenJarvis-inspired, Phase O-1)
# ---------------------------------------------------------------------------

def cmd_doctor() -> None:
    """Run honest startup health probes: camera, model, DB, disk, keys, permissions.

    Mirrors the ``/api/doctor`` HTTP endpoint but as a CLI command so the owner
    can diagnose the installation without starting the web server.  Never fakes
    a healthy result - ``.unknown(reason:)`` is the honest answer when a
    dependency cannot be verified.
    """
    from ownerai.features import is_enabled
    from ownerai.services.doctor import DoctorError, run_doctor

    if not is_enabled("DOCTOR"):
        print(
            "DOCTOR feature is not enabled. Set OWNERAI_FEATURE_DOCTOR=1 to run health probes."
        )
        return

    try:
        report = run_doctor()
    except DoctorError as exc:
        print(f"doctor: {exc}")
        return

    print("== Aegis AI Doctor Report ==")
    print(f"Overall: {report.overall.upper()}")
    print(f"Timestamp: {report.timestamp}")
    print()
    for check in report.checks:
        status = check.status.upper()
        mark = {
            "OK": "OK",
            "UNKNOWN": "??",
            "SOFT": "!!",
            "LOUD": "!!",
            "CRITICAL": "XX",
        }.get(status, "..")
        lat = f" ({check.latency_ms:.1f} ms)" if check.latency_ms is not None else ""
        print(f"  {mark} [{status:8}] {check.name}: {check.message}{lat}")
        if check.detail:
            for key, value in check.detail.items():
                if key == "latency_ms":
                    continue
                print(f"      {key}: {value}")
    print()

    if report.overall == "critical":
        print("CRITICAL: one or more dependencies are broken. Review the checks above.")
        sys.exit(1)
    elif report.overall == "degraded":
        print("DEGRADED: some dependencies are degraded but the app can still run.")
    else:
        print("OK: all core dependencies are healthy.")


def cmd_doctor_benchmark() -> None:
    """Benchmark the AI provider latency (mirrors /api/doctor/benchmark)."""
    from ownerai.features import is_enabled
    from ownerai.services.doctor import DoctorError, benchmark_provider

    if not is_enabled("DOCTOR"):
        return

    try:
        result = benchmark_provider(runs=5)
    except DoctorError as exc:
        print(f"doctor benchmark: {exc}")
        return

    print("== AI Provider Benchmark ==")
    print(f"Provider: {result.get('provider')}")
    print(f"Runs: {result.get('runs')}, Errors: {result.get('errors')}")
    latency = result.get("latency_ms")
    if latency:
        print(
            f"Latency (ms): min={latency['min']} max={latency['max']} "
            f"mean={latency['mean']} median={latency['median']}"
        )
    else:
        print("Latency: unavailable (all runs errored)")


if __name__ == "__main__":
    main()
