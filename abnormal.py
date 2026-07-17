import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk


FORMATS = [
    "OpenGL",
    "DirectX",
    "RXGB NXG",
    "RXGB TCS",
    "Half blue",
    "RXGB half blue",
    "Two channel",
    "Derivative",
]


# -----------------------------
# Core helpers
# -----------------------------

def clamp01(x):
    return max(0.0, min(1.0, x))


def clamp255(x):
    return max(0, min(255, int(round(x))))


def normalize_vec3(x, y, z):
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-12:
        return 0.0, 0.0, 1.0
    return x / length, y / length, z / length


def encode_signed(v):
    # [-1, 1] -> [0, 255]
    return clamp255((v * 0.5 + 0.5) * 255.0)


def decode_signed(v):
    # [0, 255] -> [-1, 1]
    return (v / 255.0) * 2.0 - 1.0


def open_image_as_rgba(path):
    return Image.open(path).convert("RGBA")


# -----------------------------
# Pixel conversion logic
# -----------------------------

def decode_to_normal(r, g, b, a, fmt, derivative_scale=1.0):
    """Convert one pixel from a source format into a normal vector (x, y, z)."""
    if fmt == "OpenGL":
        nx = decode_signed(r)
        ny = decode_signed(g)
        nz = decode_signed(b)
        return normalize_vec3(nx, ny, nz)

    if fmt == "DirectX":
        nx = decode_signed(r)
        ny = -decode_signed(g)
        nz = decode_signed(b)
        return normalize_vec3(nx, ny, nz)

    if fmt == "RXGB NXG":
        nx = decode_signed(a)
        ny = decode_signed(g)
        nz = decode_signed(b)
        return normalize_vec3(nx, ny, nz)

    if fmt == "RXGB TCS":
        nx = decode_signed(a)
        ny = decode_signed(g)
        nz = decode_signed(b)
        return normalize_vec3(nx, ny, nz)

    if fmt == "Half blue":
        nx = decode_signed(r)
        ny = decode_signed(g)
        # blue is half strength, so double it back on decode
        nz = decode_signed(b * 2.0)
        return normalize_vec3(nx, ny, nz)

    if fmt == "RXGB half blue":
        nx = decode_signed(a)
        ny = decode_signed(g)
        nz = decode_signed(b * 2.0)
        return normalize_vec3(nx, ny, nz)

    if fmt == "Two channel":
        nx = decode_signed(g)
        ny = decode_signed(a)
        nz_sq = 1.0 - nx * nx - ny * ny
        nz = math.sqrt(max(0.0, nz_sq))
        return normalize_vec3(nx, ny, nz)

    if fmt == "Derivative":
        # Derivative maps store slopes, not normals.
        # R = dfdx, G = dfdy. Blue is ignored.
        # Reconstruct the normal from the tangent vectors:
        # (1, 0, dfdx) x (0, 1, dfdy) = (-dfdx, -dfdy, 1)
        dfdx = decode_signed(r) * derivative_scale
        dfdy = decode_signed(g) * derivative_scale
        nx = -dfdx
        ny = -dfdy
        nz = 1.0
        return normalize_vec3(nx, ny, nz)

    raise ValueError(f"Unknown source format: {fmt}")


def encode_from_normal(nx, ny, nz, fmt, derivative_scale=1.0):
    """Convert a normal vector (x, y, z) into a target format pixel."""
    nx, ny, nz = normalize_vec3(nx, ny, nz)

    if fmt == "OpenGL":
        return (
            encode_signed(nx),
            encode_signed(ny),
            encode_signed(nz),
            255,
        )

    if fmt == "DirectX":
        return (
            encode_signed(nx),
            encode_signed(-ny),
            encode_signed(nz),
            255,
        )

    if fmt == "RXGB NXG":
        return (
            0,
            encode_signed(ny),
            encode_signed(nz),
            encode_signed(nx),
        )

    if fmt == "RXGB TCS":
        return (
            255,
            encode_signed(ny),
            encode_signed(nz),
            encode_signed(nx),
        )

    if fmt == "Half blue":
        # Blue channel is half the OpenGL blue value.
        return (
            encode_signed(nx),
            encode_signed(ny),
            clamp255(encode_signed(nz) * 0.5),
            255,
        )

    if fmt == "RXGB half blue":
        return (
            0,
            encode_signed(ny),
            clamp255(encode_signed(nz) * 0.5),
            encode_signed(nx),
        )

    if fmt == "Two channel":
        return (
            255,
            encode_signed(nx),
            255,
            encode_signed(ny),
        )

    if fmt == "Derivative":
        # Reverse the same relationship.
        # normal ~ (-dfdx, -dfdy, 1), so:
        # dfdx = -nx / nz, dfdy = -ny / nz
        if abs(nz) < 1e-8:
            dfdx = 0.0
            dfdy = 0.0
        else:
            scale = max(1e-8, derivative_scale)
            dfdx = (-nx / nz) / scale
            dfdy = (-ny / nz) / scale

        dfdx = max(-1.0, min(1.0, dfdx))
        dfdy = max(-1.0, min(1.0, dfdy))
        return (
            encode_signed(dfdx),
            encode_signed(dfdy),
            0,
            255,
        )

    raise ValueError(f"Unknown target format: {fmt}")


def convert_image(input_image, source_fmt, target_fmt, derivative_scale=1.0):
    src = input_image.convert("RGBA")
    w, h = src.size
    out = Image.new("RGBA", (w, h))
    src_px = src.load()
    out_px = out.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = src_px[x, y]
            nx, ny, nz = decode_to_normal(r, g, b, a, source_fmt, derivative_scale)
            out_px[x, y] = encode_from_normal(nx, ny, nz, target_fmt, derivative_scale)

    return out


# -----------------------------
# GUI
# -----------------------------

class NormalMapConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Abnormal (get it because it's irregular normals-)")
        self.geometry("1060x720")
        self.minsize(920, 620)

        self.input_path = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="")
        self.source_fmt = tk.StringVar(value="OpenGL")
        self.target_fmt = tk.StringVar(value="DirectX")
        self.derivative_scale = tk.DoubleVar(value=1.0)

        self.original_image = None
        self.preview_image = None
        self.preview_tk = None

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")

        file_box = ttk.LabelFrame(top, text="Files", padding=10)
        file_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ttk.Label(file_box, text="Input:").grid(row=0, column=0, sticky="w")
        ttk.Entry(file_box, textvariable=self.input_path).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(file_box, text="Browse...", command=self.browse_input).grid(row=0, column=2)

        ttk.Label(file_box, text="Output:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(file_box, textvariable=self.output_path).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(file_box, text="Save As...", command=self.browse_output).grid(row=1, column=2, pady=(8, 0))

        file_box.columnconfigure(1, weight=1)

        fmt_box = ttk.LabelFrame(top, text="Conversion", padding=10)
        fmt_box.pack(side="right", fill="y")

        ttk.Label(fmt_box, text="Source format:").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(fmt_box, self.source_fmt, self.source_fmt.get(), *FORMATS).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(fmt_box, text="Target format:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.OptionMenu(fmt_box, self.target_fmt, self.target_fmt.get(), *FORMATS).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))

        #ttk.Label(fmt_box, text="Derivative scale:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        #ttk.Spinbox(fmt_box, from_=0.01, to=1000.0, increment=0.1, textvariable=self.derivative_scale, width=10).grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))

        ttk.Button(fmt_box, text="Convert", command=self.convert).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        fmt_box.columnconfigure(1, weight=1)

        mid = ttk.Frame(outer)
        mid.pack(fill="both", expand=True, pady=(12, 0))

        preview_box = ttk.LabelFrame(mid, text="Preview", padding=10)
        preview_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.preview_label = ttk.Label(preview_box, text="Load an image to preview it here.", anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        info_box = ttk.LabelFrame(mid, text="Notes", padding=10)
        info_box.pack(side="right", fill="both", expand=False)

        notes = (
            'OpenGL "purple": Regular normal maps we all know and love. Used in most games.\n\n'
            'DirectX "purple but flipped": Used in TSS and LDK, flipped version of OpenGL.\n\n'
            'RXGB NXG "trans blue": Used in NXG and DX11 games.\n\n'
            'RXGB TCS "trans pink": Used in classic games and maybe more.\n\n'
            'Half blue "gray": Used in NXG and DX11 games.\n\n'
            'RXGB half blue "trans teal": Used rarely in NXG and DX11 games.\n\n'
            'Two channel "trans pink but weird": Used rarely in NXG and DX11 games.\n\n'
            'Derivative "yellowish green": Used in TSS.'
        )
        ttk.Label(info_box, text=notes, justify="left").pack(anchor="w")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(12, 0))

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="Load Input", command=self.load_input).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Open Output Folder", command=self.open_output_folder).pack(side="right")

    def browse_input(self):
        path = filedialog.askopenfilename(
            title="Choose input image",
            filetypes=[
                ("Image files", "*.png *.tga *.bmp *.jpg *.jpeg *.dds *.webp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_path.set(path)
            self.load_input()

    def browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Choose output image",
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("TGA", "*.tga"),
                ("BMP", "*.bmp"),
                ("JPEG", "*.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.output_path.set(path)

    def load_input(self):
        path = self.input_path.get().strip()
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Missing file", "The selected input file does not exist.")
            return
        try:
            self.original_image = open_image_as_rgba(path)
            self.show_preview(self.original_image)
            self.status.set(f"Loaded: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    def show_preview(self, image):
        # Make the preview fit in the panel while keeping the aspect ratio.
        preview = image.copy()
        preview.thumbnail((500, 500))
        self.preview_image = preview
        self.preview_tk = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_tk, text="")

    def convert(self):
        if self.original_image is None:
            self.load_input()
        if self.original_image is None:
            return

        out_path = self.output_path.get().strip()
        if not out_path:
            self.browse_output()
            out_path = self.output_path.get().strip()
            if not out_path:
                return

        try:
            converted = convert_image(
                self.original_image,
                self.source_fmt.get(),
                self.target_fmt.get(),
                float(self.derivative_scale.get()),
            )
            converted.save(out_path)
            self.status.set(f"Saved: {out_path}")
            self.show_preview(converted)
        except Exception as exc:
            messagebox.showerror("Conversion failed", str(exc))

    def open_output_folder(self):
        out_path = self.output_path.get().strip()
        if not out_path:
            return
        folder = os.path.dirname(os.path.abspath(out_path))
        if not os.path.isdir(folder):
            return
        try:
            os.startfile(folder)  # Windows
        except Exception:
            messagebox.showinfo("Folder", folder)


def main():
    app = NormalMapConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
