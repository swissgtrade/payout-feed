"""Outil de mesure : cliquez sur le certificat pour obtenir les coordonnées x,y."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = ROOT / "assets" / "template-payout.png"
DESIGN_SIZE = (1500, 1075)


class MeasureApp:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.original = Image.open(image_path).convert("RGB")
        self.design_w, self.design_h = DESIGN_SIZE
        self.img_w, self.img_h = self.original.size

        self.points: list[tuple[int, int, int, int]] = []
        self.labels = ("amount", "program_name", "username", "date")

        self.root = tk.Tk()
        self.root.title(f"Mesure certificat — {image_path.name}")

        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=8, pady=6)

        tk.Button(toolbar, text="Changer d'image", command=self.load_image).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Annuler dernier point", command=self.undo_point).pack(side=tk.LEFT, padx=6)
        tk.Button(toolbar, text="Copier config JSON", command=self.copy_json).pack(side=tk.LEFT, padx=6)
        tk.Button(toolbar, text="Réinitialiser", command=self.reset_points).pack(side=tk.LEFT)

        self.info = tk.Label(
            self.root,
            text=self.help_text(),
            justify=tk.LEFT,
            font=("Segoe UI", 10),
        )
        self.info.pack(fill=tk.X, padx=10)

        self.canvas = tk.Canvas(self.root, cursor="crosshair", bg="#111111")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status = tk.Label(self.root, text="", anchor="w", font=("Consolas", 10))
        self.status.pack(fill=tk.X, padx=10, pady=6)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.root.bind("<Configure>", self.on_resize)

        self.tk_image: ImageTk.PhotoImage | None = None
        self.display_scale = 1.0
        self.render_image()

    def help_text(self) -> str:
        return (
            "Cliquez sur le centre de chaque zone de texte dans l'ordre :\n"
            "1. Montant  2. Programme  3. Prénom  4. Date\n"
            f"Canvas de référence : {self.design_w}×{self.design_h} px"
        )

    def to_design_coords(self, canvas_x: float, canvas_y: float) -> tuple[int, int]:
        x = int(round(canvas_x / self.display_scale))
        y = int(round(canvas_y / self.display_scale))
        x = max(0, min(self.design_w, x))
        y = max(0, min(self.design_h, y))
        return x, y

    def render_image(self) -> None:
        self.canvas.update_idletasks()
        max_w = max(self.canvas.winfo_width(), 900)
        max_h = max(self.canvas.winfo_height(), 600)
        scale = min(max_w / self.img_w, max_h / self.img_h, 1.0)
        self.display_scale = scale

        display_w = int(self.img_w * scale)
        display_h = int(self.img_h * scale)
        resized = self.original.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.config(width=display_w, height=display_h)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        for index, (x, y, dx, dy) in enumerate(self.points):
            label = self.labels[index] if index < len(self.labels) else f"point_{index + 1}"
            self.draw_marker(dx, dy, label, x, y)

    def draw_marker(self, dx: int, dy: int, label: str, x: int, y: int) -> None:
        r = 6
        self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r, outline="#00ff88", width=2)
        self.canvas.create_line(dx - 14, dy, dx + 14, dy, fill="#00ff88")
        self.canvas.create_line(dx, dy - 14, dx, dy + 14, fill="#00ff88")
        self.canvas.create_text(dx + 10, dy - 12, anchor=tk.NW, fill="#00ff88", text=f"{label}\n[{x}, {y}]")

    def on_resize(self, _event: object) -> None:
        self.render_image()

    def on_motion(self, event: tk.Event) -> None:
        x, y = self.to_design_coords(event.x, event.y)
        self.status.config(text=f"Souris : [{x}, {y}]  |  Points : {len(self.points)}/4")

    def on_click(self, event: tk.Event) -> None:
        x, y = self.to_design_coords(event.x, event.y)
        self.points.append((x, y, event.x, event.y))
        label = self.labels[len(self.points) - 1] if len(self.points) <= len(self.labels) else f"point_{len(self.points)}"
        self.draw_marker(event.x, event.y, label, x, y)
        self.status.config(text=f"Ajouté {label} : [{x}, {y}]")

        if len(self.points) == 4:
            self.status.config(text="4 points enregistrés. Utilisez « Copier config JSON ».")

    def undo_point(self) -> None:
        if self.points:
            self.points.pop()
        self.render_image()

    def reset_points(self) -> None:
        self.points.clear()
        self.render_image()
        self.status.config(text="Points réinitialisés.")

    def build_positions(self) -> dict[str, list[int]]:
        positions: dict[str, list[int]] = {}
        for index, (x, y, _, _) in enumerate(self.points):
            if index < len(self.labels):
                positions[self.labels[index]] = [x, y]
        return positions

    def copy_json(self) -> None:
        if len(self.points) < 4:
            messagebox.showwarning("Mesure incomplète", "Placez les 4 points avant de copier.")
            return

        positions = self.build_positions()
        snippet = json.dumps(positions, indent=2, ensure_ascii=False)
        self.root.clipboard_clear()
        self.root.clipboard_append(snippet)
        messagebox.showinfo(
            "Copié",
            "Positions copiées dans le presse-papiers.\n\n"
            "Collez-les dans config.json → certificate.fields.*.position",
        )

    def load_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Choisir une image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("Tous", "*.*")],
        )
        if not path:
            return
        self.image_path = Path(path)
        self.original = Image.open(self.image_path).convert("RGB")
        self.img_w, self.img_h = self.original.size
        self.reset_points()
        self.root.title(f"Mesure certificat — {self.image_path.name}")
        self.info.config(text=self.help_text())

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    image_path = DEFAULT_IMAGE
    if not image_path.exists():
        messagebox.showerror("Image introuvable", f"Fichier manquant : {image_path}")
        return
    MeasureApp(image_path).run()


if __name__ == "__main__":
    main()
