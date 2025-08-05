import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from utils.remove_bg import remove_background
from utils.merge import merge_images
from utils.filters import apply_sepia, apply_blur, apply_sharpen, apply_grayscale
import threading
import asyncio
import websockets
import io
import base64
import json

def resize_keep_aspect_ratio(image, max_size):
    original_width, original_height = image.size
    max_width, max_height = max_size
    ratio = min(max_width / original_width, max_height / original_height)
    new_size = (int(original_width * ratio), int(original_height * ratio))
    return image.resize(new_size, Image.Resampling.LANCZOS)

def compress_image_to_base64(pil_image):
    buffer = io.BytesIO()
    resized = pil_image.resize((800, 600))
    resized.save(buffer, format="PNG", quality=50)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

class ImageState:
    def __init__(self, image, filter_choice, bg_path):
        self.image = image
        self.filter_choice = filter_choice
        self.bg_path = bg_path

class ImageEditorTab:
    def __init__(self, parent, ws_connection, loop, app):
        self.parent = parent
        self.ws_connection = ws_connection
        self.loop = loop
        self.app = app

        self.image_path = None
        self.bg_path = None
        self.input_image = None
        self.output_image = None
        self.selected_filter = tk.StringVar(value="Tanpa Filter")
        self.canvas_orientation = tk.StringVar(value="Horizontal")

        self.canvas_width = 1000
        self.canvas_height = 600

        self.undo_stack = []
        self.redo_stack = []

        self.setup_ui()

    def setup_ui(self):
        top_frame = tk.Frame(self.parent, bg="#f0f0f0")
        top_frame.pack(pady=5, fill="x")

        tk.Label(top_frame, text="Cut & Filter", font=("Helvetica", 16), bg="#f0f0f0").pack()

        action_frame = tk.Frame(self.parent, bg="#f0f0f0")
        action_frame.pack(pady=5)

        tk.Button(action_frame, text="\U0001F4C1 Pilih Gambar", command=self.load_image).grid(row=0, column=0, padx=5)
        tk.Button(action_frame, text="\U0001F304 Pilih Latar Belakang", command=self.load_background).grid(row=0, column=1, padx=5)

        ttk.Combobox(action_frame, textvariable=self.selected_filter,
                     values=["Tanpa Filter", "Sepia", "Blur", "Sharpen", "Grayscale"],
                     state="readonly", width=15).grid(row=0, column=2, padx=5)

        self.canvas = tk.Canvas(self.parent, width=self.canvas_width, height=self.canvas_height,
                                bg="white", bd=2, relief="sunken")
        self.canvas.pack(pady=5)

        control_frame = tk.Frame(self.parent, bg="#f0f0f0")
        control_frame.pack(pady=5)

        tk.Button(control_frame, text="↩️ Undo", command=self.undo, width=10).pack(side="left", padx=10)
        tk.Button(control_frame, text="↪️ Redo", command=self.redo, width=10).pack(side="left", padx=10)

        tk.Label(control_frame, text="Orientasi Canvas:", bg="#f0f0f0").pack(side="left", padx=10)
        orientation_menu = ttk.Combobox(
            control_frame, textvariable=self.canvas_orientation,
            values=["Horizontal", "Vertical"], state="readonly", width=12
        )
        orientation_menu.pack(side="left")
        orientation_menu.bind("<<ComboboxSelected>>", self.change_orientation)

        tk.Button(control_frame, text="✨ Proses Gambar", command=self.process_image, width=15).pack(side="left", padx=10)
        tk.Button(control_frame, text="\U0001F4BE Simpan Hasil", command=self.save_image, width=15).pack(side="left", padx=10)

    def change_orientation(self, event=None):
        orientation = self.canvas_orientation.get()
        if orientation == "Horizontal":
            self.canvas_width, self.canvas_height = 900, 600
        else:
            self.canvas_width, self.canvas_height = 400, 600

        self.canvas.config(width=self.canvas_width, height=self.canvas_height)
        if self.output_image:
            self.show_image(self.output_image)

    def show_image(self, image):
        resized = resize_keep_aspect_ratio(image, (self.canvas_width, self.canvas_height))
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        x = (self.canvas_width - resized.width) // 2
        y = (self.canvas_height - resized.height) // 2
        self.canvas.create_image(x, y, anchor="nw", image=self.tk_image)

    def broadcast_image(self):
        if self.ws_connection and self.output_image:
            try:
                encoded = compress_image_to_base64(self.output_image)
                message = {
                    "type": "image_upload",
                    "filename": os.path.basename(self.image_path or "gambar.png"),
                    "image_data": encoded
                }
                asyncio.run_coroutine_threadsafe(
                    self.ws_connection.send(json.dumps(message)),
                    self.loop
                )
            except Exception as e:
                print(f"Send error: {e}")


    def load_image(self):
        filepath = filedialog.askopenfilename(
            title="Pilih Gambar Utama",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")],
            initialdir=os.path.abspath("images")
        )
        if filepath:
            self.image_path = filepath
            self.input_image = Image.open(filepath).convert("RGBA")
            self.output_image = self.input_image.copy()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.undo_stack.append(ImageState(self.output_image.copy(), "Tanpa Filter", None))
            self.show_image(self.output_image)
            self.broadcast_image()
            self.app.rename_tab(self.parent, filepath)

    def load_background(self):
        filepath = filedialog.askopenfilename(
            title="Pilih Gambar Latar Belakang",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")],
            initialdir=os.path.abspath("backgrounds")
        )
        if filepath:
            self.bg_path = filepath
            messagebox.showinfo("Info", "Latar belakang dipilih.")

    def process_image(self):
        if not self.image_path:
            messagebox.showwarning("Peringatan", "Unggah gambar terlebih dahulu.")
            return

        fg = remove_background(self.image_path)
        combined = merge_images(self.bg_path, fg) if self.bg_path else fg

        filter_choice = self.selected_filter.get()
        if filter_choice == "Sepia":
            filtered = apply_sepia(combined)
        elif filter_choice == "Blur":
            filtered = apply_blur(combined)
        elif filter_choice == "Sharpen":
            filtered = apply_sharpen(combined)
        elif filter_choice == "Grayscale":
            filtered = apply_grayscale(combined)
        else:
            filtered = combined

        self.output_image = filtered
        self.show_image(filtered)
        self.broadcast_image()

        self.undo_stack.append(ImageState(filtered.copy(), filter_choice, self.bg_path))
        self.redo_stack.clear()

    def save_image(self):
        if not self.output_image:
            messagebox.showwarning("Peringatan", "Tidak ada gambar untuk disimpan.")
            return

        os.makedirs("results", exist_ok=True)
        name_only = os.path.splitext(os.path.basename(self.image_path))[0] if self.image_path else "gambar"

        i = 1
        while True:
            new_name = f"{name_only}_edit({i}).png"
            output_path = os.path.join("results", new_name)
            if not os.path.exists(output_path):
                break
            i += 1

        self.output_image.save(output_path)
        messagebox.showinfo("Tersimpan", f"Gambar disimpan di {output_path}")

    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            state = self.undo_stack[-1]
            self.output_image = state.image.copy()
            self.selected_filter.set(state.filter_choice)
            self.bg_path = state.bg_path
            self.show_image(self.output_image)
            self.broadcast_image()

    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            self.output_image = state.image.copy()
            self.selected_filter.set(state.filter_choice)
            self.bg_path = state.bg_path
            self.show_image(self.output_image)
            self.broadcast_image()

    def load_external_image(self, image, filename="Gambar"):
        self.output_image = image
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.undo_stack.append(ImageState(image.copy(), "Tanpa Filter", None))
        self.show_image(image)
        self.app.rename_tab(self.parent, filename)


class BackgroundRemoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cut & Filter - Penghapus Latar Belakang")
        self.root.geometry("1024x720")
        self.root.configure(bg="#f0f0f0")

        self.editor_tabs = {}
        self.filename_counter = {}

        # === Frame utama tab bar ===
        tab_bar_frame = tk.Frame(self.root, bg="#f0f0f0")
        tab_bar_frame.pack(side="top", fill="x", padx=10, pady=5)

        # === Scrollable canvas untuk tab ===
        self.tab_canvas = tk.Canvas(tab_bar_frame, height=30, bg="#f0f0f0", highlightthickness=0)
        self.tab_canvas.pack(side="left", fill="x", expand=True)

        self.tab_scroll_frame = tk.Frame(self.tab_canvas, bg="#f0f0f0")
        self.tab_window = self.tab_canvas.create_window((0, 0), window=self.tab_scroll_frame, anchor="nw")

        self.tab_scroll_frame.bind("<Configure>", self._on_tab_frame_configure)
        self.tab_canvas.bind("<Configure>", self._on_canvas_configure)

        # === Tombol + dan 🗑️ tetap di kanan ===
        self.button_frame = tk.Frame(tab_bar_frame, bg="#f0f0f0")
        self.button_frame.pack(side="right")

        self.add_tab_button = tk.Button(self.button_frame, text="➕", command=self.add_new_tab,
                                        bd=0, padx=6, pady=2, font=("Arial", 12), bg="#f0f0f0",
                                        activebackground="#e0e0e0")
        self.add_tab_button.pack(side="left", padx=(0, 4))

        self.close_tab_button = tk.Button(self.button_frame, text="🗑️", command=self.close_current_tab,
                                          bd=0, padx=6, pady=2, font=("Arial", 12), bg="#f0f0f0",
                                          activebackground="#e0e0e0")
        self.close_tab_button.pack(side="left")

        # === Frame isi tab ===
        self.tab_content_frame = tk.Frame(self.root, bg="#ffffff")
        self.tab_content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.ws_uri = "ws://192.168.30.134:8000/ws/image"
        self.ws_connection = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_ws_client, daemon=True).start()

        self.root.bind("<Control-t>", lambda event: self.add_new_tab())
        self.root.bind("<Control-T>", lambda event: self.add_new_tab())
        self.root.bind("<Control-w>", lambda event: self.close_current_tab())
        self.root.bind("<Control-W>", lambda event: self.close_current_tab())
        self.root.bind("<Control-z>", lambda event: self.call_undo())
        self.root.bind("<Control-Z>", lambda event: self.call_undo())
        self.root.bind("<Control-y>", lambda event: self.call_redo())
        self.root.bind("<Control-Y>", lambda event: self.call_redo())
        self.root.bind("<Control-Tab>", lambda event: self.next_tab())
        self.root.bind("<Control-Shift-Tab>", lambda event: self.previous_tab())

        self.add_new_tab()

    def _on_tab_frame_configure(self, event):
        self.tab_canvas.configure(scrollregion=self.tab_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        canvas_width = event.width
        self.tab_canvas.itemconfig(self.tab_window, width=canvas_width)

    def add_new_tab(self, image=None, filename=None):
        tab_name = os.path.basename(filename) if filename else "Tab Baru"
        tab_frame = tk.Frame(self.tab_content_frame, bg="#f0f0f0")
        editor = ImageEditorTab(tab_frame, self.ws_connection, self.loop, self)
        self.editor_tabs[tab_frame] = editor

        tab_button = tk.Button(self.tab_scroll_frame, text=tab_name,
                               command=lambda: self.select_tab(tab_frame),
                               relief="raised", bd=1, padx=8, pady=2)
        tab_button.pack(side="left", padx=2)

        tab_frame._tab_button = tab_button
        self.select_tab(tab_frame)

        if image:
            editor.load_external_image(image, filename)

    def rename_tab(self, frame, filename):
        name = os.path.basename(filename)
        base, ext = os.path.splitext(name)
        count = self.filename_counter.get(name, 0)
        if count > 0:
            name = f"{base}({count}){ext}"
        self.filename_counter[os.path.basename(filename)] = count + 1
        frame._tab_button.config(text=name)

    def select_tab(self, frame):
        for f in self.editor_tabs:
            f.pack_forget()
            f._tab_button.config(relief="raised")
        frame.pack(fill="both", expand=True)
        frame._tab_button.config(relief="sunken")
        self.current_tab = frame

    def close_current_tab(self):
        if hasattr(self, 'current_tab') and self.current_tab in self.editor_tabs:
            frame = self.current_tab
            frame.pack_forget()
            frame._tab_button.destroy()
            del self.editor_tabs[frame]
            self.current_tab = None
            if self.editor_tabs:
                last_tab = list(self.editor_tabs.keys())[-1]
                self.select_tab(last_tab)

    def start_ws_client(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_ws())

    async def connect_ws(self):
        try:
            async with websockets.connect(self.ws_uri, max_size=2**22) as ws:
                self.ws_connection = ws
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, str):
                        try:
                            data = json.loads(msg)
                            if data.get("type") == "image_upload" and "image_data" in data:
                                image_bytes = base64.b64decode(data["image_data"])
                                img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                                filename = data.get("filename", f"Gambar_{len(self.editor_tabs)+1}.png")
                                self.root.after(0, lambda: self.add_new_tab(img, filename))
                        except json.JSONDecodeError:
                            print("Invalid JSON received")
        except Exception as e:
            print(f"WebSocket error: {e}")

    
    def call_undo(self):
        if hasattr(self, 'current_tab') and self.current_tab in self.editor_tabs:
            self.editor_tabs[self.current_tab].undo()

    def call_redo(self):
        if hasattr(self, 'current_tab') and self.current_tab in self.editor_tabs:
            self.editor_tabs[self.current_tab].redo()
    
    def next_tab(self):
        tabs = list(self.editor_tabs.keys())
        if hasattr(self, 'current_tab') and self.current_tab in tabs:
            idx = tabs.index(self.current_tab)
            next_idx = (idx + 1) % len(tabs)
            self.select_tab(tabs[next_idx])

    def previous_tab(self):
        tabs = list(self.editor_tabs.keys())
        if hasattr(self, 'current_tab') and self.current_tab in tabs:
            idx = tabs.index(self.current_tab)
            prev_idx = (idx - 1) % len(tabs)
            self.select_tab(tabs[prev_idx])


if __name__ == "__main__":
    root = tk.Tk()
    app = BackgroundRemoverApp(root)
    root.mainloop()
