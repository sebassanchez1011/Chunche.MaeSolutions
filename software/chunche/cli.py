from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .system import ChuncheSystem


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chunche", description="Software de control para Chunche.")
    parser.add_argument("--config", default="config/hardware.yaml", help="Ruta a hardware.yaml")
    parser.add_argument("--data-dir", default="data", help="Directorio de datos")

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Inicia la interfaz web local")
    run.add_argument("--mode", choices=["sim", "hardware"], default="sim")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8000)

    capture = sub.add_parser("capture", help="Captura una imagen de prueba")
    capture.add_argument("--mode", choices=["sim", "hardware"], default="sim")
    capture.add_argument("--session-id", type=int)
    capture.add_argument("--kind", default="initial")

    sub.add_parser("self-test", help="Ejecuta una sesion simulada completa")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        system = ChuncheSystem(mode=args.mode, config_path=args.config, data_dir=args.data_dir)
        try:
            import uvicorn
        except ImportError:
            print("Falta uvicorn/FastAPI. Instala: pip install -r requirements.txt", file=sys.stderr)
            return 2
        from .webapp import create_app

        app = create_app(system)
        print(f"Chunche listo en http://{args.host}:{args.port} (modo {args.mode})")
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "capture":
        system = ChuncheSystem(mode=args.mode, config_path=args.config, data_dir=args.data_dir)
        session_id = args.session_id
        if not session_id:
            session = system.create_session("captura-cli", "cli", "Captura creada desde CLI")
            session_id = int(session["id"])
        result = system.capture(session_id, kind=args.kind)
        print(result["path"])
        return 0

    if args.command == "self-test":
        system = ChuncheSystem(mode="sim", config_path=args.config, data_dir=args.data_dir)
        session = system.create_session("self-test", "cli", "Prueba simulada automatica")
        capture = system.capture(session["id"], "initial")
        analysis = system.analyze(session["id"])
        if analysis["detections"]:
            system.confirm_action(session["id"], int(analysis["detections"][0]["id"]))
        report = system.generate_report(session["id"])
        print("Captura:", capture["path"])
        print("Detecciones:", len(analysis["detections"]))
        print("Reporte:", report["path"])
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

