# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Encode, then draw: what a caller does each frame (generate_modules, then a modules_to_... output), in one call for the geometry
tests. A start payload is encoded with its metadata."""

from .. import MarkerKind, Options, Payload, Point, Quad, StartMetadata, Vertex, generate_modules, modules_to_indexed, modules_to_quads, modules_to_triangles


def generate_quads(payload: Payload, options: Options, origin: Point) -> list[Quad]:
    return modules_to_quads(generate_modules(payload), options, origin)


def generate_start_quads(payload: Payload, metadata: StartMetadata, options: Options, origin: Point) -> list[Quad]:
    return modules_to_quads(generate_modules(payload.with_kind(MarkerKind.SEQUENCE_START), metadata), options, origin)


def generate_triangles(payload: Payload, options: Options, origin: Point) -> list[Vertex]:
    return modules_to_triangles(generate_modules(payload), options, origin)


def generate_start_triangles(payload: Payload, metadata: StartMetadata, options: Options, origin: Point) -> list[Vertex]:
    return modules_to_triangles(generate_modules(payload.with_kind(MarkerKind.SEQUENCE_START), metadata), options, origin)


def generate_indexed(payload: Payload, options: Options, origin: Point, base_vertex: int = 0) -> tuple[list[Vertex], list[int]]:
    return modules_to_indexed(generate_modules(payload), options, origin, base_vertex)


def generate_start_indexed(payload: Payload, metadata: StartMetadata, options: Options, origin: Point, base_vertex: int = 0) -> tuple[list[Vertex], list[int]]:
    return modules_to_indexed(generate_modules(payload.with_kind(MarkerKind.SEQUENCE_START), metadata), options, origin, base_vertex)


def to_triangles(quads: list[Quad]) -> list[Vertex]:
    """The documented vertex order of a quad, (TL, TR, BL) (BL, TR, BR), written independently of the library."""
    vertices: list[Vertex] = []
    for quad in quads:
        luma = 0 if quad.dark else 255
        tl, tr, br, bl = (
            Vertex(quad.left, quad.top, luma),
            Vertex(quad.right, quad.top, luma),
            Vertex(quad.right, quad.bottom, luma),
            Vertex(quad.left, quad.bottom, luma),
        )
        vertices += (tl, tr, bl, bl, tr, br)
    return vertices


def to_indexed(quads: list[Quad], base_vertex: int) -> tuple[list[Vertex], list[int]]:
    """The documented indexed order: 4 vertices (TL, TR, BR, BL) and indices (0,1,3)(3,1,2) per quad, plus the base vertex."""
    vertices: list[Vertex] = []
    indices: list[int] = []
    for quad in quads:
        luma = 0 if quad.dark else 255
        first = base_vertex + len(vertices)
        vertices += (
            Vertex(quad.left, quad.top, luma),
            Vertex(quad.right, quad.top, luma),
            Vertex(quad.right, quad.bottom, luma),
            Vertex(quad.left, quad.bottom, luma),
        )
        indices += (first, first + 1, first + 3, first + 3, first + 1, first + 2)
    return vertices, indices
