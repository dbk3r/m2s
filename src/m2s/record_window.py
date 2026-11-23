"""Desktop window for one recording job at a time."""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from m2s.record_audio import (
    LEVEL_ZONE,
    NEEDLE_CENTS,
    cents,
    check_take,
    dbfs,
    detect_hz,
    display_band,
    level_hint,
    write_wav24,
)
from m2s.record_jobs import (
    DYNAMICS,
    NOTES,
    SAMPLE_RATE,
    Job,
    JobStatus,
    add_singer,
    current_singer,
    discover,
    list_singers,
    nearest_note,
    note_hz,
    remember_singer,
    remove_singer,
)


class Tuner(QWidget):
    def __init__(self):
        super().__init__()
        self.cents_off: float | None = None
        self.setMinimumHeight(72)

    def paintEvent(self, _event):
        painter = QPainter(self)
        width = self.width()
        mid = width / 2
        painter.fillRect(self.rect(), QColor("#f4f1ea"))
        painter.setPen(QColor("#8a8478"))
        painter.drawLine(int(mid), 8, int(mid), self.height() - 8)
        if self.cents_off is None:
            return
        band = display_band(self.cents_off)
        color = {"mittig": "#2f7d4a", "daneben": "#b5791a", "weit": "#a33b32"}[band]
        offset = max(-NEEDLE_CENTS, min(NEEDLE_CENTS, self.cents_off)) / NEEDLE_CENTS * (width * 0.45)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(int(mid + offset) - 8, self.height() // 2 - 8, 16, 16)


class LevelMeter(QWidget):
    """Bar from -60 to 0 dBFS. The tinted span is the zone for leise or laut."""

    def __init__(self):
        super().__init__()
        self.level_db = -120.0
        self.dynamic = "leise"
        self.setMinimumHeight(56)

    def paintEvent(self, _event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        painter.fillRect(self.rect(), QColor("#f4f1ea"))
        low, high = LEVEL_ZONE[self.dynamic]
        painter.fillRect(
            _x(width, low),
            8,
            max(1, _x(width, high) - _x(width, low)),
            height - 16,
            QColor("#cfe3d4"),
        )
        painter.setPen(QColor("#2f7d4a"))
        painter.drawText(8, height - 8, self.dynamic)
        level_x = _x(width, self.level_db)
        color = "#2f7d4a" if level_hint(self.level_db, self.dynamic) == "passt" else "#a33b32"
        painter.fillRect(0, height // 2 - 6, level_x, 12, QColor(color))


def _x(width: int, level_db: float) -> int:
    share = (min(0.0, max(-60.0, level_db)) + 60.0) / 60.0
    return int(share * width)


class RecordWindow(QMainWindow):
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.singer: str | None = None
        self.jobs: list[Job] = []
        self.status: JobStatus | None = None
        self.current: Job | None = None
        self.recording = False
        self.frames: list[np.ndarray] = []
        self.latest = np.zeros(0, dtype=np.float32)
        self._audio_lock = threading.Lock()
        self.take: np.ndarray | None = None
        self.stream = None
        self.setWindowTitle("Aufnahme")
        self.resize(1100, 720)
        self._build()
        self._load_singers(current_singer(root))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_meter)
        self.timer.start(50)
        self._open_stream()

    def _build(self):
        shell = QWidget()
        self.setCentralWidget(shell)
        row = QHBoxLayout(shell)
        side = QVBoxLayout()
        singer_row = QHBoxLayout()
        self.singer_box = QComboBox()
        self.singer_box.setMinimumWidth(160)
        self.add_singer_button = QPushButton("Hinzufügen")
        self.remove_singer_button = QPushButton("Entfernen")
        singer_row.addWidget(self.singer_box, 1)
        singer_row.addWidget(self.add_singer_button)
        singer_row.addWidget(self.remove_singer_button)
        self.singer_box.currentIndexChanged.connect(self._on_singer)
        self.add_singer_button.clicked.connect(self._add_singer)
        self.remove_singer_button.clicked.connect(self._remove_singer)
        side.addLayout(singer_row)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(320)
        self.tree.itemSelectionChanged.connect(self._on_select)
        side.addWidget(self.tree, 1)
        row.addLayout(side)
        main = QVBoxLayout()
        row.addLayout(main, 1)
        self.meta = QLabel()
        self.meta.setWordWrap(True)
        self.lyric = QLabel("Keine Datei")
        self.lyric.setWordWrap(True)
        self.lyric.setStyleSheet("font-size: 32px;")
        self.hint = QLabel("Atem vor und nach der Zeile. Kein Vibrato. Kein Hall.")
        self.cents_label = QLabel("kein Ton")
        self.cents_label.setStyleSheet("font-size: 20px;")
        self.tuner = Tuner()
        self.level_meter = LevelMeter()
        self.level = QLabel("Pegel")
        self.level.setStyleSheet("font-size: 22px;")
        self.duration = QLabel("")
        self.duration.setStyleSheet("font-size: 22px;")
        self.device = QComboBox()
        self._fill_devices()
        self.device.currentIndexChanged.connect(self._open_stream)
        buttons = QHBoxLayout()
        self.record_button = QPushButton("Aufnahme · Leertaste")
        self.play_button = QPushButton("Anhören")
        self.keep_button = QPushButton("Übernehmen")
        self.drop_button = QPushButton("Verwerfen")
        self.skip_button = QPushButton("Ganze Note auslassen")
        self.next_button = QPushButton("Nächste")
        for button in (
            self.record_button,
            self.play_button,
            self.keep_button,
            self.drop_button,
            self.skip_button,
            self.next_button,
        ):
            buttons.addWidget(button)
        self.record_button.clicked.connect(self._toggle_record)
        self._space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._space.setAutoRepeat(False)
        self._space.setContext(Qt.ApplicationShortcut)
        self._space.activated.connect(self._toggle_record)
        self.play_button.clicked.connect(self._play)
        self.keep_button.clicked.connect(self._keep)
        self.drop_button.clicked.connect(self._drop)
        self.skip_button.clicked.connect(self._skip_note)
        self.next_button.clicked.connect(self._select_first_open)
        self.play_button.setEnabled(False)
        self.keep_button.setEnabled(False)
        self.drop_button.setEnabled(False)
        main.addWidget(self.meta)
        main.addWidget(self.lyric)
        main.addWidget(self.hint)
        main.addWidget(self.tuner)
        main.addWidget(self.cents_label)
        main.addWidget(self.level_meter)
        main.addWidget(self.level)
        main.addWidget(self.duration)
        main.addWidget(self.device)
        main.addLayout(buttons)
        main.addStretch(1)

    def _load_singers(self, select: str | None):
        names = list_singers(self.root)
        if select not in names:
            select = names[0] if names else None
        self.singer_box.blockSignals(True)
        self.singer_box.clear()
        self.singer_box.addItems(names)
        if select:
            self.singer_box.setCurrentText(select)
        self.singer_box.blockSignals(False)
        self.remove_singer_button.setEnabled(bool(names) and not self.recording)
        self._open_singer(select)

    def _on_singer(self):
        name = self.singer_box.currentText()
        if name and name != self.singer:
            self._open_singer(name)

    def _open_singer(self, name: str | None):
        self._abort_take()
        if self.status is not None:
            self.status.close()
            self.status = None
        self.singer = name
        self.current = None
        self.take = None
        remember_singer(self.root, name)
        if name:
            folder = self.root / name
            self.jobs = discover(folder)
            self.status = JobStatus(folder / "record.sqlite")
            self.setWindowTitle(f"Aufnahme · {name}")
        else:
            self.jobs = []
            self.setWindowTitle("Aufnahme")
            self.lyric.setText("Zuerst einen Sänger hinzufügen")
        self._fill_tree()
        self._select_first_open()
        self._show_job()

    def _add_singer(self):
        self._space.setEnabled(False)
        try:
            name, ok = QInputDialog.getText(self, "Sänger", "Name des Sängers")
        finally:
            self._space.setEnabled(True)
        if not ok:
            return
        try:
            add_singer(self.root, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Sänger", str(exc))
            return
        except FileExistsError:
            QMessageBox.warning(self, "Sänger", "Diesen Sänger gibt es schon.")
            return
        self._load_singers(name.strip())

    def _remove_singer(self):
        if not self.singer:
            return
        folder = self.root / self.singer
        wavs = list(folder.rglob("*.wav"))
        text = f"{self.singer} entfernen?"
        if wavs:
            text = f"{self.singer} und {len(wavs)} Aufnahmen entfernen?"
        self._space.setEnabled(False)
        try:
            answer = QMessageBox.question(self, "Sänger", text)
        finally:
            self._space.setEnabled(True)
        if answer != QMessageBox.StandardButton.Yes:
            return
        remove_singer(self.root, self.singer)
        self._load_singers(None)

    def _abort_take(self):
        with self._audio_lock:
            self.recording = False
            self.frames = []
        self.take = None
        self.record_button.setText("Aufnahme · Leertaste")

    def _fill_devices(self):
        self.device.clear()
        try:
            import sounddevice as sd
        except ImportError:
            self.device.addItem("sounddevice fehlt", None)
            return
        default = sd.default.device[0]
        for index, info in enumerate(sd.query_devices()):
            if info["max_input_channels"] < 1:
                continue
            label = info["name"]
            if index == default:
                label = f"{label} (Standard)"
            self.device.addItem(label, index)

    def _fill_tree(self):
        self.tree.clear()
        self.items: dict[str, QTreeWidgetItem] = {}
        if self.status is None:
            return
        for note in NOTES:
            note_item = QTreeWidgetItem([note])
            self.tree.addTopLevelItem(note_item)
            for dynamic in DYNAMICS:
                dynamic_item = QTreeWidgetItem([dynamic])
                note_item.addChild(dynamic_item)
                for job in self.jobs:
                    if job.note == note and job.dynamic == dynamic:
                        label = f"{job.number:03d}  {job.text}"
                        item = QTreeWidgetItem([label])
                        item.setData(0, Qt.UserRole, job.key)
                        dynamic_item.addChild(item)
                        self.items[job.key] = item
            note_item.setExpanded(False)
        self._paint_states()

    def _paint_states(self):
        for job in self.jobs:
            item = self.items[job.key]
            state = self.status.status(job)
            item.setText(0, f"{job.number:03d}  {job.text}  [{state}]")

    def _job_by_key(self, key: str) -> Job | None:
        for job in self.jobs:
            if job.key == key:
                return job
        return None

    def _on_select(self):
        items = self.tree.selectedItems()
        if not items:
            return
        key = items[0].data(0, Qt.UserRole)
        if not key:
            return
        job = self._job_by_key(key)
        if job is None:
            return
        self.current = job
        self.take = None
        self._show_job()

    def _show_job(self):
        job = self.current
        if job is None:
            self.record_button.setEnabled(False)
            self.play_button.setEnabled(False)
            self.keep_button.setEnabled(False)
            self.drop_button.setEnabled(False)
            return
        hz = note_hz(job.note)
        state = self.status.status(job)
        self.meta.setText(f"{job.note} · {hz:.1f} Hz · {job.dynamic} · {state}")
        self.lyric.setText(job.text)
        if self.take is None:
            self.duration.setText("")
            self.duration.setStyleSheet("font-size: 22px;")
        ready = self.take is not None and not self.recording
        self.play_button.setEnabled(ready)
        self.keep_button.setEnabled(ready)
        self.drop_button.setEnabled(ready)
        self.record_button.setText("Stopp · Leertaste" if self.recording else "Aufnahme · Leertaste")
        self.record_button.setEnabled(self.current is not None)
        self.singer_box.setEnabled(not self.recording)
        self.add_singer_button.setEnabled(not self.recording)
        self.remove_singer_button.setEnabled(self.singer is not None and not self.recording)

    def _select_first_open(self):
        for job in self.jobs:
            if self.status.status(job) == "open":
                item = self.items[job.key]
                item.parent().parent().setExpanded(True)
                item.parent().setExpanded(True)
                self.tree.setCurrentItem(item)
                return

    def _open_stream(self):
        self._close_stream()
        device = self.device.currentData()
        if device is None:
            return
        try:
            import sounddevice as sd
        except ImportError:
            self.level.setText("sounddevice ist nicht installiert")
            return

        def callback(indata, _frames, _time, status):
            if status:
                return
            chunk = indata[:, 0].copy()
            with self._audio_lock:
                self.latest = chunk
                if self.recording:
                    self.frames.append(chunk)

        self.stream = sd.InputStream(
            device=device,
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=2048,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()

    def _close_stream(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _refresh_meter(self):
        with self._audio_lock:
            samples = self.latest
        level = dbfs(samples)
        dynamic = self.current.dynamic if self.current is not None else "leise"
        hint = level_hint(level, dynamic)
        self.level_meter.dynamic = dynamic
        self.level_meter.level_db = level
        self.level_meter.update()
        self.level.setText(f"{hint} · {level:.0f} dBFS · Auftrag {dynamic}")
        job = self.current
        if job is None or samples.size < 1024:
            return
        hz = detect_hz(samples, SAMPLE_RATE)
        if hz is None:
            self.cents_label.setText("kein Ton")
            self.tuner.cents_off = None
        else:
            off = float(cents(hz, note_hz(job.note)))
            self.cents_label.setText(
                f"gesungen {nearest_note(hz)} · {off:+.0f} Cent · Anzeige, keine Abnahme"
            )
            self.tuner.cents_off = off
        self.tuner.update()

    def _record(self):
        if self.current is None:
            return
        with self._audio_lock:
            self.frames = []
            self.recording = True
        self.take = None
        self.duration.setText("")
        self.duration.setStyleSheet("font-size: 22px;")
        self.record_button.setText("Stopp · Leertaste")
        self.singer_box.setEnabled(False)
        self.add_singer_button.setEnabled(False)
        self.remove_singer_button.setEnabled(False)
        self.keep_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.drop_button.setEnabled(False)

    def _toggle_record(self):
        if self.recording:
            self._stop()
        else:
            self._record()

    def _stop(self):
        with self._audio_lock:
            self.recording = False
            frames = list(self.frames)
            self.frames = []
        if not frames:
            self._show_job()
            return
        self.take = np.concatenate(frames)
        job = self.current
        if job is None:
            self._show_job()
            return
        check = check_take(self.take, SAMPLE_RATE, job.note, job.dynamic)
        color = "#2f7d4a" if check.usable else "#a33b32"
        self.duration.setStyleSheet(f"font-size: 22px; color: {color};")
        self.duration.setText(check.line())
        self._show_job()

    def _play(self):
        if self.take is None:
            return
        import sounddevice as sd

        sd.play(self.take, SAMPLE_RATE)

    def _keep(self):
        job = self.current
        if job is None or self.take is None:
            return
        write_wav24(job.wav_path, self.take, SAMPLE_RATE)
        self.status.mark(job, "done")
        self.take = None
        self._paint_states()
        self._show_job()
        self._select_first_open()

    def _drop(self):
        self.take = None
        self._show_job()

    def _skip_note(self):
        if self.current is None:
            return
        self.status.skip_note(self.jobs, self.current.note)
        self._paint_states()
        self._select_first_open()

    def closeEvent(self, event):
        self._close_stream()
        super().closeEvent(event)


def run_record_app(root: Path) -> None:
    app = QApplication([])
    window = RecordWindow(root)
    window.show()
    app.exec()
