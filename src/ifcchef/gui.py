"""Eenvoudig venster: kies OTL en IFC, klik op Opschonen.

Het opschonen draait in een apart proces (``ifcchef.worker``), zodat het venster
blijft reageren, ook tijdens het opslaan van grote IFC-bestanden.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ifcchef import __version__, config, pipeline, worker
from ifcchef.cleaner import CleanReport

POLL_MS = 200


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.otl_var = tk.StringVar(value=str(config.DEFAULT_OTL_PATH))
        self.ifc_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Kies een IFC-bestand.")
        self._messages: queue.Queue = queue.Queue()
        self._process: subprocess.Popen | None = None
        self._target: Path | None = None
        self._phase = ""
        self._started = 0.0
        self._build()
        for var in (self.otl_var, self.ifc_var):
            var.trace_add("write", lambda *_: self._update_state())
        self._update_state()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(5, weight=1)

        ttk.Label(self, text="OTL-bestand:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.otl_var, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=8
        )
        self.otl_button = ttk.Button(self, text="OTL kiezen…", command=self._choose_otl)
        self.otl_button.grid(row=0, column=2, sticky="ew")

        ttk.Label(self, text="IFC-bestand:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.ifc_var, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=8
        )
        self.ifc_button = ttk.Button(self, text="IFC kiezen…", command=self._choose_ifc)
        self.ifc_button.grid(row=1, column=2, sticky="ew")

        self.run_button = ttk.Button(self, text="Opschonen", command=self._run)
        self.run_button.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 4))

        ttk.Label(self, textvariable=self.status_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=4
        )
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self.output = tk.Text(self, height=16, wrap="word", state="disabled")
        self.output.grid(row=5, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.output.yview)
        scrollbar.grid(row=5, column=3, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

    def _choose_otl(self) -> None:
        current = Path(self.otl_var.get())
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Kies de OTL",
            initialdir=str(current.parent) if current.parent.exists() else None,
            filetypes=[("Excel-bestanden", "*.xlsx"), ("Alle bestanden", "*.*")],
        )
        if chosen:
            self.otl_var.set(str(Path(chosen)))

    def _choose_ifc(self) -> None:
        current = Path(self.ifc_var.get()) if self.ifc_var.get() else None
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Kies een IFC-bestand",
            initialdir=str(current.parent) if current else None,
            filetypes=[("IFC-bestanden", "*.ifc"), ("Alle bestanden", "*.*")],
        )
        if chosen:
            self.ifc_var.set(str(Path(chosen)))
            self.status_var.set("Klik op Opschonen.")

    @property
    def busy(self) -> bool:
        return self._process is not None

    def _update_state(self) -> None:
        ready = Path(self.otl_var.get()).is_file() and Path(self.ifc_var.get()).is_file()
        self.run_button.configure(state="normal" if ready and not self.busy else "disabled")
        for button in (self.otl_button, self.ifc_button):
            button.configure(state="disabled" if self.busy else "normal")

    def _run(self) -> None:
        ifc_path = Path(self.ifc_var.get())
        otl_path = Path(self.otl_var.get())
        self._target = pipeline.output_path(ifc_path)
        overwrite = False
        if self._target.exists():
            overwrite = messagebox.askyesno(
                "Bestand bestaat al",
                f"{self._target.name} bestaat al.\n\nWil je het overschrijven?",
                parent=self,
            )
            if not overwrite:
                return

        command = [sys.executable, "-m", "ifcchef.worker", str(ifc_path), str(otl_path)]
        if overwrite:
            command.append("--overwrite")
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read_worker, args=(self._process,), daemon=True).start()

        self._set_output("")
        self._phase = "Starten…"
        self._started = time.monotonic()
        self._update_state()
        self.progress.start(15)
        self.after(POLL_MS, self._poll)

    def _read_worker(self, process: subprocess.Popen) -> None:
        """Leest de uitvoer van het workerproces (in een thread) en zet die in de queue."""
        result = None
        other: list[str] = []
        for line in process.stdout:
            line = line.rstrip("\n")
            if line.startswith(worker.STATUS):
                self._messages.put(("status", line.removeprefix(worker.STATUS)))
            elif line.startswith(worker.RESULT):
                result = json.loads(line.removeprefix(worker.RESULT))
            elif line.strip():
                other.append(line)
        process.wait()
        if result is None:
            details = "\n".join(other[-15:]) or f"exitcode {process.returncode}"
            result = {"ok": False, "message": f"Het opschonen is onverwacht gestopt.\n\n{details}"}
        self._messages.put(("result", result))

    def _poll(self) -> None:
        while True:
            try:
                kind, value = self._messages.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self._phase = value
            elif kind == "result":
                self._finish(value)
                return
        self.status_var.set(f"{self._phase}  ({self._elapsed()})")
        self.after(POLL_MS, self._poll)

    def _elapsed(self) -> str:
        seconds = int(time.monotonic() - self._started)
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _finish(self, result: dict) -> None:
        self._process = None
        self.progress.stop()
        self._update_state()
        if result["ok"]:
            target = Path(result["output"])
            report = CleanReport.from_dict(result["report"])
            self.status_var.set(f"Klaar in {self._elapsed()}. Opgeslagen als {target.name}")
            self._set_output(f"Opgeslagen: {target}\n\n{report.summary()}")
        else:
            self.status_var.set("Opschonen mislukt.")
            self._set_output(f"Fout: {result['message']}")
            messagebox.showerror("Opschonen mislukt", result["message"], parent=self)

    def on_close(self) -> None:
        if self.busy:
            stop = messagebox.askyesno(
                "Bezig met opschonen",
                "Het opschonen is nog bezig.\n\nWil je stoppen en het venster sluiten?",
                parent=self,
            )
            if not stop:
                return
            self._process.kill()
            self._process.wait()
            if self._target:
                for leftover in pipeline.leftover_temp_files(self._target):
                    leftover.unlink(missing_ok=True)
        self.winfo_toplevel().destroy()

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")


def main() -> int:
    root = tk.Tk()
    root.title(f"IfcChef {__version__} - ILS opschonen")
    root.minsize(640, 440)
    app = App(root)
    app.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0
