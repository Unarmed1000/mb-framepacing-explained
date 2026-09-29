#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Generate the dynamic resolution example video: rotating 3D objects rendered at a resolution that changes with the load, scaled
up to a fixed output, with a HUD drawn on top at the output resolution.

Every frame renders the scene (cubes and an octahedron over a sky and ground) at its render scale with OpenGL, through moderngl in
a headless context: perspective-correct texturing, mipmaps built by the driver and sampled with trilinear and anisotropic filtering,
a depth buffer, and 4x MSAA for the edges. The frame is then scaled up to the output size with a plain bilinear filter, and the HUD,
the render scale and size in text and a small diagram of the render box inside the output, is drawn at the output resolution, so it
stays sharp while the scene under it softens and sharpens.

The render scale follows the dynamic resolution chart's model (tools/timing_diagrams/generate_dynamic_resolution.py), at half speed
so the changes are easy to follow, then rises back to full resolution and holds it. --pattern model-low stretches that curve down
to MODEL_LOW, still within the ranges games use; --pattern jumps and --pattern low instead jump between full resolution and a half or a quarter, holding each for
JUMP_FRAMES. --pattern fixed is render scale, a scale that never changes: the frame cut across the middle, through
every object, the top half at full resolution and the bottom half at --scale, for the whole clip. --pattern fsr cuts the same
way, both halves at --scale: above scaled up with the plain bilinear filter, below with AMD's FSR 1 (its EASU upscale and RCAS
sharpening, from the headers in fsr1/, MIT licence). The objects are flat-shaded, or with --textured carry textures (bricks on the cubes, a fine checkerboard on the
octahedron): fine surface detail is what a lower resolution loses first, so the change shows more. With --ui the frame also
carries a game's UI panel twice: on the left drawn at the render resolution and scaled up with the scene, on the right drawn at
the output resolution after scaling up, so the one blurs as the resolution drops and the other stays sharp. --pattern fixed
with --ui has no cut: the whole frame is at --scale, and the two panels are the comparison.

Every clip loops seamlessly: every object turns a whole number of times in it, the textures do not change over time, and the render
scale starts where it ends (the model) or jumps there as it does in the middle (jumps, low).

OpenGL 3.3 comes from the system (4.3 for FSR 1, so not on macOS): the GPU driver on Windows, macOS and a Linux desktop; on Linux without a display (a build server),
EGL with Mesa's software renderer (Debian and Ubuntu: apt install libegl1 libgl1-mesa-dri).

Run from the repository's .venv:
  python tools/frame_pacing_video/generate_render_scale_video.py [--pattern model|model-low|jumps|low|fixed|fsr] [--scale S] [--textured] [--ui]
    [--output FILE]
    [--ffmpeg PATH]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import functools
import math
import random
import struct
import subprocess
import sys
from pathlib import Path

import moderngl
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "timing_diagrams"))

from generate_dynamic_resolution import MAX_RAISE, MAX_SCALE, dynamic_run  # noqa: E402
from generate_videos import find_ffmpeg  # noqa: E402

OUTPUT_W, OUTPUT_H = 1280, 384
FPS = 60
SLOWDOWN = 2  # each frame of the model is shown for this many video frames
MODEL_FRAMES = 300  # 5 s: the model at half speed, its rise back to full resolution, and a hold
JUMP_FRAMES = 120  # 2 s at each resolution
# The low resolution each jumping pattern drops to, per axis, and the lowest the stretched model reaches
JUMP_LOW = {"jumps": 0.5, "low": 0.25}
FIXED_FRAMES = 240  # 4 s
FSR_DIR = Path(__file__).resolve().parent / "fsr1"  # AMD's FSR 1 headers
FSR_SHARPNESS = 0.2  # RCAS: stops below its strongest sharpening
MODEL_LOW = 0.6  # games' 60 fps modes mostly stay above about 58 % (Digital Foundry's measurements)
MSAA_SAMPLES = 4
ANISOTROPY = 16.0
TEXTURE_SIZE = 256
CAMERA = 6.0  # the camera's distance from an object's centre, in object units
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "out" / "dynamic-resolution"
# A game UI panel's size, and where its two copies go, in output pixels: the left one drawn at the render resolution
UI_PANEL = (340, 104)
UI_LEFT = (16, 264)
UI_RIGHT = (OUTPUT_W - 16 - UI_PANEL[0], 264)

type Vec = tuple[float, float, float]
type Colour = tuple[int, int, int]

CUBE_VERTICES: tuple[Vec, ...] = tuple((x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0))
CUBE_FACES = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
OCTA_VERTICES: tuple[Vec, ...] = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
OCTA_FACES = ((0, 2, 4), (4, 2, 1), (1, 2, 5), (5, 2, 0), (0, 4, 3), (4, 1, 3), (1, 5, 3), (5, 0, 3))
# A face's texture coordinates, corner by corner: the whole texture on every face
QUAD_UV = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
TRIANGLE_UV = ((0.0, 1.0), (1.0, 1.0), (0.5, 0.0))
LIGHT: Vec = (-0.45, -0.7, -0.55)  # towards the light, in camera space (y down, z into the screen)
SKY = ((62, 84, 118), (150, 166, 188))  # top, and bottom of the whole frame
GROUND = ((96, 104, 82), (54, 62, 48))  # horizon, bottom
HORIZON = 0.62  # of the frame's height, from the top

OBJECT_VERTEX_SHADER = """
#version 330
uniform mat3 rotation;
uniform vec2 centre;    // pixels, from the top left
uniform float unit;     // pixels per object unit at the object's centre
uniform vec2 viewport;  // pixels
uniform float camera;
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
out vec3 normal;
out vec2 uv;
void main() {
    vec3 p = rotation * in_position;
    float depth = camera + p.z;
    vec2 screen = centre + p.xy * unit * camera / depth;
    vec2 ndc = vec2(screen.x / viewport.x * 2.0 - 1.0, 1.0 - screen.y / viewport.y * 2.0);
    // w is the depth, so the rasterizer interpolates the texture coordinates perspective-correctly
    gl_Position = vec4(ndc * depth, p.z / 2.0 * depth, depth);
    normal = rotation * in_normal;
    uv = in_uv;
}
"""

OBJECT_FRAGMENT_SHADER = """
#version 330
uniform vec3 light;
uniform vec3 colour;
uniform bool textured;
uniform sampler2D surface;
in vec3 normal;
in vec2 uv;
out vec4 fragment;
void main() {
    float brightness = 0.38 + 0.62 * max(0.0, dot(normalize(normal), light));
    vec3 base = textured ? texture(surface, uv).rgb : colour;
    fragment = vec4(base * brightness, 1.0);
}
"""

QUAD_VERTEX_SHADER = """
#version 430
in vec2 in_position;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

# FSR 1's two passes around AMD's headers: the callbacks they read the image through, and the pass itself at every output pixel
EASU_SHADER = """
#define FSR_EASU_F 1
uniform sampler2D source;
uniform uvec4 con0;
uniform uvec4 con1;
uniform uvec4 con2;
uniform uvec4 con3;
AF4 FsrEasuRF(AF2 p) { return textureGather(source, p, 0); }
AF4 FsrEasuGF(AF2 p) { return textureGather(source, p, 1); }
AF4 FsrEasuBF(AF2 p) { return textureGather(source, p, 2); }
FSR_HEADER
out vec4 fragment;
void main() {
    AF3 colour;
    FsrEasuF(colour, AU2(gl_FragCoord.xy), con0, con1, con2, con3);
    fragment = vec4(colour, 1.0);
}
"""

RCAS_SHADER = """
#define FSR_RCAS_F 1
uniform sampler2D source;
uniform uvec4 con;
AF4 FsrRcasLoadF(ASU2 p) { return texelFetch(source, p, 0); }
void FsrRcasInputF(inout AF1 r, inout AF1 g, inout AF1 b) {}
FSR_HEADER
out vec4 fragment;
void main() {
    AF1 r, g, b;
    FsrRcasF(r, g, b, AU2(gl_FragCoord.xy), con);
    fragment = vec4(r, g, b, 1.0);
}
"""

BACKGROUND_VERTEX_SHADER = """
#version 330
in vec2 in_position;
out float down;  // 0 at the top of the frame, 1 at the bottom
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    down = (1.0 - in_position.y) / 2.0;
}
"""

BACKGROUND_FRAGMENT_SHADER = """
#version 330
uniform vec3 sky_top;
uniform vec3 sky_bottom;
uniform vec3 ground_top;
uniform vec3 ground_bottom;
uniform float horizon;
in float down;
out vec4 fragment;
void main() {
    vec3 colour = down < horizon
        ? mix(sky_top, sky_bottom, down)
        : mix(ground_top, ground_bottom, (down - horizon) / (1.0 - horizon));
    fragment = vec4(colour, 1.0);
}
"""


def scales(pattern: str) -> list[float]:
    """The render scale of every video frame. model: the chart's model at half speed, then back up to full resolution, held to the
    end of the clip, so the last frame leads into the first. model-low: the same curve stretched so its lowest point is MODEL_LOW.
    jumps and low: full resolution, then JUMP_LOW, JUMP_FRAMES each."""
    if pattern in JUMP_LOW:
        return [MAX_SCALE] * JUMP_FRAMES + [JUMP_LOW[pattern]] * JUMP_FRAMES
    model = dynamic_run().scale
    while model[-1] < MAX_SCALE:
        model.append(min(MAX_SCALE, model[-1] + MAX_RAISE))
    if pattern == "model-low":
        lowest = min(model)
        model = [MAX_SCALE - (MAX_SCALE - value) * (MAX_SCALE - MODEL_LOW) / (MAX_SCALE - lowest) for value in model]
    values = [value for value in model for _ in range(SLOWDOWN)]
    if len(values) > MODEL_FRAMES:
        raise ValueError(f"the render scale needs {len(values)} frames, more than the clip's {MODEL_FRAMES}")
    return values + [MAX_SCALE] * (MODEL_FRAMES - len(values))


def fsr_shader(body: str) -> str:
    """An FSR 1 pass as a GLSL 4.3 fragment shader: AMD's headers, 32-bit, with the pass's callbacks between them."""
    common = (FSR_DIR / "ffx_a.h").read_text(encoding="utf-8")
    fsr = (FSR_DIR / "ffx_fsr1.h").read_text(encoding="utf-8")
    source = "#version 430\n#define A_GPU 1\n#define A_GLSL 1\n" + common + body.replace("FSR_HEADER", fsr)
    # The headers name each other in comments only, and moderngl would try to resolve those includes
    return source.replace("#include", "include")


def float_bits(value: float) -> int:
    """A 32-bit float's bits as an unsigned integer, as FSR 1 passes its constants."""
    return struct.unpack("<I", struct.pack("<f", value))[0]


def easu_constants(width: int, height: int, out_w: int, out_h: int) -> tuple[tuple[int, ...], ...]:
    """FsrEasuCon from ffx_fsr1.h: the whole input image, `width` x `height`, scaled up to `out_w` x `out_h`."""
    sx, sy = width / out_w, height / out_h
    rx, ry = 1 / width, 1 / height
    return (
        tuple(float_bits(v) for v in (sx, sy, 0.5 * sx - 0.5, 0.5 * sy - 0.5)),
        tuple(float_bits(v) for v in (rx, ry, rx, -ry)),
        tuple(float_bits(v) for v in (-rx, 2 * ry, rx, 2 * ry)),
        (float_bits(0.0), float_bits(4 * ry), 0, 0),
    )


def normalised(v: Vec) -> Vec:
    length = math.sqrt(sum(c * c for c in v))
    return (v[0] / length, v[1] / length, v[2] / length)


def rotation(ax: float, ay: float) -> tuple[float, ...]:
    """A turn by `ax` about the x axis, then by `ay` about the y axis, as a 3 x 3 matrix in OpenGL's column order."""
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    # Rows of Ry(ay) @ Rx(ax)
    rows = ((cy, sy * sx, sy * cx), (0.0, cx, -sx), (-sy, cy * sx, cy * cx))
    return tuple(rows[row][column] for column in range(3) for row in range(3))


def mesh(vertices: tuple[Vec, ...], faces: tuple[tuple[int, ...], ...]) -> bytes:
    """The object as triangles, every vertex its position, its face's outward normal and its texture coordinate (a quad as two
    triangles), packed as 32-bit floats."""
    data: list[float] = []
    for face in faces:
        a, b, c = (vertices[i] for i in face[:3])
        normal = normalised(
            (
                (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
                (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
            )
        )
        centroid = [sum(vertices[i][k] for i in face) / len(face) for k in range(3)]
        if sum(n * p for n, p in zip(normal, centroid, strict=True)) < 0:
            normal = (-normal[0], -normal[1], -normal[2])  # the objects are convex around their centre: point it outwards
        uv = QUAD_UV if len(face) == 4 else TRIANGLE_UV
        for triangle in ((0, 1, 2), (0, 2, 3)) if len(face) == 4 else ((0, 1, 2),):
            for corner in triangle:
                data += [*vertices[face[corner]], *normal, *uv[corner]]
    return struct.pack(f"{len(data)}f", *data)


# The textures


@functools.cache
def brick_texture(colour: Colour) -> Image.Image:
    """Bricks in `colour`, each a little lighter or darker, in darker mortar, with a fine grain: the same every run."""
    size = TEXTURE_SIZE
    generator = random.Random(f"bricks {colour}")
    image = Image.new("RGB", (size, size), (round(colour[0] * 0.5), round(colour[1] * 0.5), round(colour[2] * 0.5)))
    draw = ImageDraw.Draw(image)
    rows, brick_w = 8, size / 4
    row_h = size / rows
    for row in range(rows):
        x = -brick_w / 2 * (row % 2)
        while x < size:
            shade = generator.uniform(0.82, 1.12)
            fill = (min(255, round(colour[0] * shade)), min(255, round(colour[1] * shade)), min(255, round(colour[2] * shade)))
            draw.rectangle([x + 3, row * row_h + 3, x + brick_w - 3, (row + 1) * row_h - 3], fill=fill)
            x += brick_w
    return grained(image, generator)


@functools.cache
def checker_texture(colour: Colour) -> Image.Image:
    """A fine checkerboard of `colour` and a darker shade, with thin light lines between the squares and a fine grain."""
    size, cells = TEXTURE_SIZE, 16
    generator = random.Random(f"checker {colour}")
    dark = (round(colour[0] * 0.55), round(colour[1] * 0.55), round(colour[2] * 0.55))
    image = Image.new("RGB", (size, size), colour)
    draw = ImageDraw.Draw(image)
    cell = size / cells
    for row in range(cells):
        for column in range(cells):
            if (row + column) % 2:
                draw.rectangle([column * cell, row * cell, (column + 1) * cell, (row + 1) * cell], fill=dark)
    for i in range(cells + 1):
        draw.line([(i * cell, 0), (i * cell, size)], fill=(235, 240, 230), width=1)
        draw.line([(0, i * cell), (size, i * cell)], fill=(235, 240, 230), width=1)
    return grained(image, generator)


def grained(image: Image.Image, generator: random.Random) -> Image.Image:
    """`image` with a fine grain of up to +-24 per channel, drawn from `generator`."""
    grain = Image.frombytes("L", image.size, bytes(generator.randrange(104, 153) for _ in range(image.width * image.height)))
    return ImageChops.add(image, grain.convert("RGB"), 1.0, -128)


# The renderer


def open_context(require: int) -> moderngl.Context:
    """A headless OpenGL context of at least version `require` (330: 3.3): the system's driver, or on Linux without a display,
    EGL (Mesa's software renderer)."""
    try:
        return moderngl.create_standalone_context(require=require)
    except Exception:
        if not sys.platform.startswith("linux"):
            raise
        return moderngl.create_standalone_context(require=require, backend="egl")  # pyright: ignore[reportArgumentType]  # the stub types it as a dict


class Renderer:
    """The scene in OpenGL: the objects' meshes and textures, the shaders, and a multisampled framebuffer per render size."""

    def __init__(self, require: int = 330) -> None:
        self.ctx: moderngl.Context = open_context(require)
        self.objects: moderngl.Program = self.ctx.program(vertex_shader=OBJECT_VERTEX_SHADER, fragment_shader=OBJECT_FRAGMENT_SHADER)
        self.background: moderngl.Program = self.ctx.program(vertex_shader=BACKGROUND_VERTEX_SHADER, fragment_shader=BACKGROUND_FRAGMENT_SHADER)
        quad = self.ctx.buffer(struct.pack("8f", -1, -1, 1, -1, -1, 1, 1, 1))
        self.quad: moderngl.VertexArray = self.ctx.vertex_array(self.background, [(quad, "2f", "in_position")])  # pyright: ignore[reportUnknownMemberType]
        self.meshes: dict[str, moderngl.VertexArray] = {
            name: self.ctx.vertex_array(self.objects, [(self.ctx.buffer(mesh(vertices, faces)), "3f 3f 2f", "in_position", "in_normal", "in_uv")])  # pyright: ignore[reportUnknownMemberType]
            for name, (vertices, faces) in {"cube": (CUBE_VERTICES, CUBE_FACES), "octahedron": (OCTA_VERTICES, OCTA_FACES)}.items()
        }
        self.textures: dict[tuple[str, Colour], moderngl.Texture] = {}
        self.targets: dict[tuple[int, int], tuple[moderngl.Framebuffer, moderngl.Framebuffer]] = {}
        self.fsr: tuple[moderngl.Program, moderngl.Program, moderngl.VertexArray, moderngl.VertexArray] | None = None

    def texture(self, kind: str, colour: Colour) -> moderngl.Texture:
        """A texture with its mipmaps, built by the driver, filtered trilinearly and anisotropically, repeating."""
        key = (kind, colour)
        if key not in self.textures:
            image = brick_texture(colour) if kind == "bricks" else checker_texture(colour)
            texture = self.ctx.texture(image.size, 3, image.tobytes(), alignment=1)
            texture.build_mipmaps()
            texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            texture.anisotropy = ANISOTROPY
            self.textures[key] = texture
        return self.textures[key]

    def target(self, width: int, height: int) -> tuple[moderngl.Framebuffer, moderngl.Framebuffer]:
        """A multisampled framebuffer to draw into, and a plain one to resolve it into and read back."""
        if (width, height) not in self.targets:
            samples = self.ctx.framebuffer(
                color_attachments=[self.ctx.renderbuffer((width, height), 4, samples=MSAA_SAMPLES)],
                depth_attachment=self.ctx.depth_renderbuffer((width, height), samples=MSAA_SAMPLES),
            )
            resolved = self.ctx.framebuffer(color_attachments=[self.ctx.renderbuffer((width, height), 4)])
            self.targets[(width, height)] = (samples, resolved)
        return self.targets[(width, height)]

    def fsr1(self, image: Image.Image, out_w: int, out_h: int) -> Image.Image:
        """`image` scaled up to `out_w` x `out_h` with FSR 1: EASU, then RCAS on its result. Needs an OpenGL 4.3 context."""
        if self.fsr is None:
            quad = self.ctx.buffer(struct.pack("8f", -1, -1, 1, -1, -1, 1, 1, 1))
            easu = self.ctx.program(vertex_shader=QUAD_VERTEX_SHADER, fragment_shader=fsr_shader(EASU_SHADER))
            rcas = self.ctx.program(vertex_shader=QUAD_VERTEX_SHADER, fragment_shader=fsr_shader(RCAS_SHADER))
            self.fsr = (
                easu,
                rcas,
                self.ctx.vertex_array(easu, [(quad, "2f", "in_position")]),  # pyright: ignore[reportUnknownMemberType]
                self.ctx.vertex_array(rcas, [(quad, "2f", "in_position")]),  # pyright: ignore[reportUnknownMemberType]
            )
        easu, rcas, easu_quad, rcas_quad = self.fsr
        self.ctx.disable(moderngl.DEPTH_TEST)
        # The image's rows go in top first, so the texture's first row is the image's top; the output reads back the same way
        source = self.ctx.texture(image.size, 3, image.tobytes(), alignment=1)
        source.repeat_x = source.repeat_y = False
        upscaled = self.ctx.texture((out_w, out_h), 4)
        upscaled.repeat_x = upscaled.repeat_y = False
        target = self.ctx.framebuffer(color_attachments=[upscaled])
        target.use()
        source.use(location=0)
        easu["source"].value = 0  # pyright: ignore[reportAttributeAccessIssue]
        for name, value in zip(("con0", "con1", "con2", "con3"), easu_constants(*image.size, out_w, out_h), strict=True):
            easu[name].value = value  # pyright: ignore[reportAttributeAccessIssue]
        easu_quad.render(moderngl.TRIANGLE_STRIP)
        sharpened = self.ctx.framebuffer(color_attachments=[self.ctx.renderbuffer((out_w, out_h), 4)])
        sharpened.use()
        upscaled.use(location=0)
        rcas["source"].value = 0  # pyright: ignore[reportAttributeAccessIssue]
        rcas["con"].value = (float_bits(2**-FSR_SHARPNESS), 0, 0, 0)  # pyright: ignore[reportAttributeAccessIssue]
        rcas_quad.render(moderngl.TRIANGLE_STRIP)
        result = Image.frombytes("RGB", (out_w, out_h), sharpened.read(components=3, alignment=1))
        for resource in (source, upscaled, target, sharpened):
            resource.release()
        return result

    def render(self, width: int, height: int, frame: int, frames: int, textured: bool) -> Image.Image:
        """The scene at `width` x `height`, at `frame` of a clip of `frames` frames, flat or `textured`."""
        samples, resolved = self.target(width, height)
        samples.use()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.clear()
        for name, value in (("sky_top", SKY[0]), ("sky_bottom", SKY[1]), ("ground_top", GROUND[0]), ("ground_bottom", GROUND[1])):
            self.background[name].value = tuple(c / 255 for c in value)  # pyright: ignore[reportAttributeAccessIssue]
        self.background["horizon"].value = HORIZON  # pyright: ignore[reportAttributeAccessIssue]
        self.quad.render(moderngl.TRIANGLE_STRIP)
        # The background wrote no depth (the depth test was off), so the objects start from the cleared depth buffer
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.objects["viewport"].value = (width, height)  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["camera"].value = CAMERA  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["light"].value = normalised(LIGHT)  # pyright: ignore[reportAttributeAccessIssue]
        unit = 0.2 * height
        # One turn over the whole clip; every object turns a whole number of times about each axis, so the clip loops
        turn = 2 * math.pi * frame / frames
        scene: tuple[tuple[str, str, Colour, tuple[float, float], float, tuple[float, float]], ...] = (
            ("cube", "bricks", (214, 104, 82), (0.2, 0.52), 1.0, (0.5 + turn, 2 * turn)),
            ("octahedron", "checker", (120, 190, 110), (0.5, 0.5), 1.5, (turn, -2 * turn)),
            ("cube", "bricks", (100, 150, 220), (0.8, 0.52), 0.85, (2 * turn, 0.3 + turn)),
        )
        for name, kind, colour, (fx, fy), size, (ax, ay) in scene:
            self.objects["rotation"].value = rotation(ax, ay)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["centre"].value = (fx * width, fy * height)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["unit"].value = unit * size  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["colour"].value = tuple(c / 255 for c in colour)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["textured"].value = textured  # pyright: ignore[reportAttributeAccessIssue]
            if textured:
                self.texture(kind, colour).use(location=0)
                self.objects["surface"].value = 0  # pyright: ignore[reportAttributeAccessIssue]
            self.meshes[name].render(moderngl.TRIANGLES)
        self.ctx.copy_framebuffer(resolved, samples)
        pixels = resolved.read(components=3, alignment=1)
        # OpenGL's rows run from the bottom up
        return Image.frombytes("RGB", (width, height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def draw_hud(frame: Image.Image, scale: float, top: int = 14, upscaler: str = "") -> None:
    """The HUD at the output resolution, from `top`: the render scale (and the `upscaler`, when named) and size, and the render
    box inside the output."""
    draw = ImageDraw.Draw(frame)
    width, height = round(frame.width * scale), round(frame.height * scale)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=13)
    draw.rounded_rectangle([16, top, 452, top + 58], radius=8, fill=(18, 21, 25))
    title = f"Render scale {round(scale * 100)} %" + (f", {upscaler}" if upscaler else "")
    draw.text((28, top + 6), title, fill=(230, 237, 243), font=font)
    draw.text((28, top + 32), f"renders {width} x {height}, scaled up to {frame.width} x {frame.height}", fill=(139, 148, 158), font=small)
    # The render box inside the output, to scale
    box_h = 29
    box_w = min(96, round(box_h * frame.width / frame.height))
    x0, y0 = 336, top + 14
    draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], outline=(139, 148, 158), width=1)
    draw.rectangle([x0, y0, x0 + box_w * scale, y0 + box_h * scale], fill=(88, 166, 255))


def draw_game_ui(image: Image.Image, origin: tuple[int, int], scale: float) -> None:
    """A game's UI panel (health, ammo, the objective and a hint) at `origin` in output pixels, drawn into `image` at `scale`: 1 on
    the output, the render scale on a frame still at the render resolution."""
    draw = ImageDraw.Draw(image)

    def at(x: float, y: float) -> tuple[float, float]:
        return ((origin[0] + x) * scale, (origin[1] + y) * scale)

    def font(size: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return ImageFont.load_default(size=size * scale)

    white, grey = (230, 237, 243), (139, 148, 158)
    draw.rounded_rectangle([*at(0, 0), *at(*UI_PANEL)], radius=max(1, round(8 * scale)), fill=(18, 21, 25))
    draw.text(at(12, 12), "HEALTH", fill=grey, font=font(11))
    draw.rectangle([*at(72, 13), *at(262, 23)], fill=(48, 54, 61))
    draw.rectangle([*at(72, 13), *at(72 + 190 * 0.87, 23)], fill=(46, 160, 67))
    draw.text(at(274, 8), "87", fill=white, font=font(16))
    draw.text(at(12, 36), "AMMO", fill=grey, font=font(11))
    draw.text(at(72, 32), "24 / 120", fill=white, font=font(16))
    draw.text(at(12, 58), "Objective: reach the tower before nightfall", fill=white, font=font(13))
    draw.text(at(12, 81), "Press E to open the map, Tab for the inventory", fill=grey, font=font(11))


def draw_ui_labels(frame: Image.Image) -> None:
    """Which UI panel is which, at the output resolution above each."""
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default(size=13)
    for (x, y), label in ((UI_LEFT, "UI at the render resolution, scaled up"), (UI_RIGHT, "UI at the output resolution")):
        left, top, right, bottom = draw.textbbox((x + 8, y - 24), label, font=font)
        draw.rounded_rectangle([left - 8, top - 5, right + 8, bottom + 5], radius=6, fill=(18, 21, 25))
        draw.text((x + 8, y - 24), label, fill=(88, 166, 255), font=font)


def split_frames(renderer: Renderer, scale: float, textured: bool, fsr: bool = False) -> list[bytes]:
    """The fixed pattern: every frame at full resolution above the middle and at `scale`, scaled up, below it, with a line
    between. With `fsr` both halves are at `scale`: above scaled up bilinearly, below with FSR 1."""
    width, height = round(OUTPUT_W * scale), round(OUTPUT_H * scale)
    half = OUTPUT_H // 2
    out: list[bytes] = []
    for index in range(FIXED_FRAMES):
        small = renderer.render(width, height, index, FIXED_FRAMES, textured)
        scaled = small.resize((OUTPUT_W, OUTPUT_H), Image.Resampling.BILINEAR)  # pyright: ignore[reportUnknownMemberType]
        if fsr:
            frame, below = scaled, renderer.fsr1(small, OUTPUT_W, OUTPUT_H)
        else:
            frame, below = renderer.render(OUTPUT_W, OUTPUT_H, index, FIXED_FRAMES, textured), scaled
        frame.paste(below.crop((0, half, OUTPUT_W, OUTPUT_H)), (0, half))
        ImageDraw.Draw(frame).line([(0, half), (OUTPUT_W, half)], fill=(230, 237, 243), width=2)
        if fsr:
            draw_hud(frame, scale, upscaler="bilinear")
            draw_hud(frame, scale, OUTPUT_H - 14 - 58, "FSR 1")
        else:
            draw_hud(frame, MAX_SCALE)
            draw_hud(frame, scale, OUTPUT_H - 14 - 58)
        out.append(frame.tobytes())
    return out


def frames(renderer: Renderer, values: list[float], textured: bool = False, ui: bool = False) -> list[bytes]:
    """A frame at each render scale of `values`."""
    out: list[bytes] = []
    for index, scale in enumerate(values):
        width, height = round(OUTPUT_W * scale), round(OUTPUT_H * scale)
        scene = renderer.render(width, height, index, len(values), textured)
        if ui:
            draw_game_ui(scene, UI_LEFT, width / OUTPUT_W)  # before scaling up: at the render resolution
        frame = scene if scale == 1.0 else scene.resize((OUTPUT_W, OUTPUT_H), Image.Resampling.BILINEAR)  # pyright: ignore[reportUnknownMemberType]
        if ui:
            draw_game_ui(frame, UI_RIGHT, 1.0)  # after scaling up: at the output resolution
            draw_ui_labels(frame)
        draw_hud(frame, scale)
        out.append(frame.tobytes())
    return out


class Arguments(argparse.Namespace):
    pattern: str
    scale: float
    textured: bool
    ui: bool
    output: Path | None
    ffmpeg: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the dynamic resolution example video (H.264, for the web page).")
    _ = parser.add_argument(
        "--pattern",
        choices=("model", "model-low", *JUMP_LOW, "fixed", "fsr"),
        default="model",
        help="the render scale: the chart's model, the same down to 60 %% (model-low), jumps to half (jumps) or a quarter (low), "
        + "full resolution and --scale, the frame cut across the middle (fixed), or --scale bilinear and FSR 1, cut the same (fsr)",
    )
    _ = parser.add_argument("--scale", type=float, default=0.5, help="the fixed and fsr patterns' render scale per axis (default: 0.5)")
    _ = parser.add_argument("--textured", action="store_true", help="textures on the objects: bricks and a fine checkerboard")
    _ = parser.add_argument("--ui", action="store_true", help="a game UI panel twice: at the render resolution and at the output resolution")
    _ = parser.add_argument("--output", type=Path, default=None, help=f"the video file (default: {DEFAULT_OUTPUT_DIR}/dynamic-resolution-PATTERN.mp4)")
    _ = parser.add_argument("--ffmpeg", default=None, help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    args = parser.parse_args(namespace=Arguments())
    ffmpeg = find_ffmpeg(args.ffmpeg).path
    pattern = f"{args.pattern}-{round(args.scale * 100)}" if args.pattern in ("fixed", "fsr") else args.pattern
    suffix = ("-textured" if args.textured else "") + ("-ui" if args.ui else "")
    output = args.output or DEFAULT_OUTPUT_DIR / f"dynamic-resolution-{pattern}{suffix}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.pattern == "fsr":
        video = split_frames(Renderer(430), args.scale, args.textured, fsr=True)
    elif args.pattern == "fixed" and not args.ui:
        video = split_frames(Renderer(), args.scale, args.textured)
    else:
        values = [args.scale] * FIXED_FRAMES if args.pattern == "fixed" else scales(args.pattern)
        video = frames(Renderer(), values, args.textured, args.ui)
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUTPUT_W}x{OUTPUT_H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]  # fmt: skip
    _ = subprocess.run(command, input=b"".join(video), check=True)
    print(f"{output}: {len(video)} frames, {len(video) / FPS:g} s")


if __name__ == "__main__":
    main()
