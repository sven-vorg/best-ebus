"""
Tkinter dashboard for the eBuS analysis pipeline.

Lets you:
    1. Pick a run's output folder: a `<description>run_<timestamp>` folder
       (the description prefix is optional and arbitrary, e.g.
       `validation_1051_run_2026-08-31-21-32-52`) holding one
       `<seed>_directory` subfolder per seed, each with
       `<seed>_multirun_<type>.xml` files, as produced by
       `tools.order_output.order_output` (`SeedOutputFiles`, see
       `analysis/output_files.py`). Each seed is listed as its own
       selectable entry.
    2. Pick which analysis methods (from `dashboard.methods.METHODS`) to run
       against it, and run them in one batch.

Generated plots/files are written to `<output_folder>/plots`, matching
`analysis/analysis_main.py`. Methods run with the "Agg" matplotlib backend,
so `plt.show()` calls inside the analysis module are no-ops here - the
dashboard is a headless batch runner, not a plot viewer.

All console output produced while running is mirrored into
`<output_folder>/plots/analysis_log.txt`, same as `analysis/analysis_main.py`
used to do - a fresh log is written each time "Run selected methods" is
clicked.
"""

from __future__ import annotations

import logging
import queue
import re
import sys
import traceback
from pathlib import Path
from threading import Thread

import matplotlib
matplotlib.use("Agg")

DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent  # eBuS/
SCENARIO_ROOT = PROJECT_ROOT.parent  # scenario/
SUMO_DIR = SCENARIO_ROOT / "sumo"
SUMO_OUTPUT_DIR = SUMO_DIR / "output"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.output_files import SeedOutputFiles
from dashboard.methods import METHODS

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

_DONE = object()

SEED_DIR_PATTERN = re.compile(r"^(\d+)_directory$")
RUN_DIR_PATTERN = re.compile(r"run_(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})$")


def _seed_dirs(run_dir: Path) -> list[str]:
    """Seed numbers of the `<seed>_directory` subfolders directly under run_dir, sorted numerically."""
    if not run_dir.is_dir():
        return []
    seeds = []
    for p in run_dir.iterdir():
        if p.is_dir():
            match = SEED_DIR_PATTERN.match(p.name)
            if match:
                seeds.append(match.group(1))
    return sorted(seeds, key=int)


def _load_run_files(path: Path):
    """
    Resolve the run-files dict for path using the per-seed layout.
    Returns (resolver, message). Raises FileNotFoundError/ValueError if the
    layout doesn't match.
    """
    resolver = SeedOutputFiles(path)
    resolver.get_run_files()
    return resolver, f"Valid multi-seed run (seed: {resolver.seed})"


class QueueWriter:
    """File-like object that forwards writes into a queue for the log pane."""

    def __init__(self, log_queue: queue.Queue):
        self._queue = log_queue

    def write(self, text: str):
        text = text.rstrip("\n")
        if text:
            self._queue.put(text)

    def flush(self):
        pass


class _Tee:
    """File-like object that mirrors writes to multiple streams."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for stream in self._streams:
            stream.write(text)

    def flush(self):
        for stream in self._streams:
            stream.flush()


class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self._queue = log_queue

    def emit(self, record: logging.LogRecord):
        self._queue.put(self.format(record))


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable frame, used to hold the method checkboxes."""

    def __init__(self, container, **kwargs):
        super().__init__(container, **kwargs)

        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)

        self.body.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas_window = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(canvas_window, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)


class Dashboard(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=10)
        self.root = root
        self.output_dir: Path | None = None
        self._run_entries: dict[str, Path] = {}
        self.log_queue: queue.Queue = queue.Queue()
        self.method_vars: dict[str, tk.BooleanVar] = {}

        self._setup_logging()
        self._build_output_folder_section()
        self._build_methods_section()
        self._build_run_section()

        self.pack(fill="both", expand=True)
        self.root.after(150, self._poll_log_queue)

    # -- logging -----------------------------------------------------------

    def _setup_logging(self):
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    # -- output folder section ----------------------------------------------

    def _build_output_folder_section(self):
        frame = ttk.LabelFrame(self, text="1. Run output folder", padding=8)
        frame.pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="Detected runs:").grid(row=0, column=0, sticky="w")
        self.run_combo = ttk.Combobox(frame, state="readonly", width=40)
        self.run_combo.grid(row=0, column=1, sticky="we", padx=5)
        self.run_combo.bind("<<ComboboxSelected>>", self._on_run_selected)

        ttk.Button(frame, text="Refresh", command=self._refresh_runs).grid(row=0, column=2, padx=2)
        ttk.Button(frame, text="Browse...", command=self._browse_output_dir).grid(row=0, column=3, padx=2)

        ttk.Label(frame, text="Selected folder:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.output_dir_var = tk.StringVar(value="(none selected)")
        ttk.Entry(frame, textvariable=self.output_dir_var, state="readonly", width=70).grid(
            row=1, column=1, columnspan=3, sticky="we", padx=5, pady=(6, 0)
        )

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(4, 0)
        )

        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=f"SUMO scenario dir: {SUMO_DIR}",
            foreground="gray",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self._refresh_runs()

    def _refresh_runs(self):
        entries: dict[str, Path] = {}
        if SUMO_OUTPUT_DIR.is_dir():
            timestamps: dict[Path, str] = {}
            for p in SUMO_OUTPUT_DIR.iterdir():
                if p.is_dir():
                    match = RUN_DIR_PATTERN.search(p.name)
                    if match:
                        timestamps[p] = match.group(1)
            run_dirs = sorted(timestamps, key=lambda p: timestamps[p], reverse=True)
            for run_dir in run_dirs:
                seeds = _seed_dirs(run_dir)
                if seeds:
                    for seed in seeds:
                        entries[f"{run_dir.name} / seed {seed}"] = run_dir / f"{seed}_directory"
                else:
                    entries[run_dir.name] = run_dir

        self._run_entries = entries
        self.run_combo["values"] = list(entries.keys())
        if not entries:
            self.run_combo.set("")

    def _on_run_selected(self, _event=None):
        path = self._run_entries.get(self.run_combo.get())
        if path:
            self._set_output_dir(path)

    def _browse_output_dir(self):
        initial_dir = SUMO_OUTPUT_DIR if SUMO_OUTPUT_DIR.is_dir() else SCENARIO_ROOT
        chosen = filedialog.askdirectory(initialdir=str(initial_dir), title="Select a run output folder")
        if chosen:
            self.run_combo.set("")
            self._set_output_dir(Path(chosen))

    def _set_output_dir(self, path: Path):
        self.output_dir = path
        self.output_dir_var.set(str(path))
        try:
            _, message = _load_run_files(path)
        except (FileNotFoundError, ValueError) as exc:
            self.status_var.set(f"✗ Not a valid run folder: {exc}")
        else:
            self.status_var.set(f"✓ {message}")

    # -- methods section -----------------------------------------------------

    def _build_methods_section(self):
        frame = ttk.LabelFrame(self, text="2. Analysis methods to run", padding=8)
        frame.pack(fill="both", expand=True, pady=(0, 8))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(0, 6))
        ttk.Button(button_row, text="Select all", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(button_row, text="Select none", command=lambda: self._set_all(False)).pack(
            side="left", padx=5
        )

        scrollable = ScrollableFrame(frame)
        scrollable.pack(fill="both", expand=True)

        categories: dict[str, list] = {}
        for method in METHODS:
            categories.setdefault(method.category, []).append(method)

        for category, methods in categories.items():
            cat_frame = ttk.LabelFrame(scrollable.body, text=category, padding=6)
            cat_frame.pack(fill="x", padx=4, pady=4, anchor="w")

            for method in methods:
                var = tk.BooleanVar(value=method.default_selected)
                self.method_vars[method.name] = var
                text = method.name + (f" — {method.description}" if method.description else "")
                ttk.Checkbutton(cat_frame, text=text, variable=var).pack(anchor="w")

    def _set_all(self, value: bool):
        for var in self.method_vars.values():
            var.set(value)

    # -- run section --------------------------------------------------------

    def _build_run_section(self):
        frame = ttk.LabelFrame(self, text="3. Run", padding=8)
        frame.pack(fill="both", expand=True)

        self.run_button = ttk.Button(frame, text="Run selected methods", command=self._on_run_clicked)
        self.run_button.pack(anchor="w")

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.log_text = tk.Text(log_frame, height=14, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _on_run_clicked(self):
        if self.output_dir is None:
            messagebox.showerror("No output folder", "Select a run output folder first.")
            return

        selected = [m for m in METHODS if self.method_vars[m.name].get()]
        if not selected:
            messagebox.showinfo("Nothing selected", "Select at least one analysis method to run.")
            return

        self.run_button.configure(state="disabled")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        output_dir = self.output_dir
        Thread(target=self._worker, args=(selected, output_dir), daemon=True).start()

    def _worker(self, methods, output_dir: Path):
        original_stdout = sys.stdout
        plots_dir = output_dir / "plots"
        plots_dir.mkdir(exist_ok=True)
        log_path = plots_dir / "analysis_log.txt"

        with open(log_path, "w", encoding="utf-8") as log_file:
            sys.stdout = _Tee(QueueWriter(self.log_queue), log_file)
            try:
                try:
                    files = _load_run_files(output_dir)[0].get_run_files()
                except Exception:
                    print(f"Could not read run files from {output_dir}:")
                    print(traceback.format_exc())
                    return

                for method in methods:
                    log_file.write(f"# {method.name}\n")
                    print(f"=== Running: {method.name} ===")
                    try:
                        method.func(files, SUMO_DIR, plots_dir)
                        print(f"[OK] {method.name}")
                    except Exception:
                        print(f"[FAILED] {method.name}")
                        print(traceback.format_exc())
                    log_file.write("\n")

                print("=== All selected methods finished. ===")
            finally:
                sys.stdout = original_stdout
                self.log_queue.put(_DONE)

    def _poll_log_queue(self):
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if item is _DONE:
                self.run_button.configure(state="normal")
            else:
                self._append_log(item)
        self.root.after(150, self._poll_log_queue)

    def _append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main():
    root = tk.Tk()
    root.title("eBuS Analysis Dashboard")
    root.geometry("900x750")
    Dashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
