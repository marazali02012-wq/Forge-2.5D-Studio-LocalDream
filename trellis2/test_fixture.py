"""Synthetic, multi-mesh, UV/PBR test fixture. NOT a TRELLIS.2 generation."""
import io
import json
import struct
from PIL import Image

def glb():
    image = io.BytesIO()
    Image.new("RGBA", (4, 4), (220, 95, 35, 255)).save(image, "PNG")
    binary = bytearray()
    views = []
    def add(chunk, target=None):
        while len(binary) % 4: binary.append(0)
        entry = {"buffer": 0, "byteOffset": len(binary), "byteLength": len(chunk)}
        if target: entry["target"] = target
        views.append(entry)
        binary.extend(chunk)
        return len(views)-1
    pos = add(struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0), 34962)
    nrm = add(struct.pack("<9f", 0, 0, 1, 0, 0, 1, 0, 0, 1), 34962)
    uv = add(struct.pack("<6f", 0, 0, 1, 0, 0, 1), 34962)
    idx = add(struct.pack("<3H", 0, 1, 2), 34963)
    texture = add(image.getvalue())
    while len(binary) % 4: binary.append(0)
    data = {
      "asset": {"version": "2.0"},
      "scene": 0,
      "scenes": [{"nodes": [0]}],
      "nodes": [{"name": "root", "children": [1,2]},
                {"name": "first", "mesh": 0, "translation": [-0.5,0,0]},
                {"name": "second", "mesh": 1, "translation": [0.5,0,0]}],
      "meshes": [{"primitives": [{"attributes": {"POSITION":0,"NORMAL":1,"TEXCOORD_0":2}, "indices":3,"material":0}]},
                 {"primitives": [{"attributes": {"POSITION":0,"NORMAL":1,"TEXCOORD_0":2}, "indices":3,"material":1}]}],
      "materials": [
          {"pbrMetallicRoughness": {"baseColorTexture":{"index":0},"metallicFactor":0.0,"roughnessFactor":0.95}},
          {"alphaMode":"BLEND","doubleSided":True,"pbrMetallicRoughness":{"baseColorTexture":{"index":0},"metallicFactor":0.4,"roughnessFactor":0.5}}],
      "samplers": [{"magFilter":9729,"minFilter":9729,"wrapS":33071,"wrapT":33071}],
      "textures": [{"sampler":0,"source":0}],
      "images": [{"bufferView":texture,"mimeType":"image/png"}],
      "buffers": [{"byteLength":len(binary)}],
      "bufferViews": views,
      "accessors": [
          {"bufferView":pos,"componentType":5126,"count":3,"type":"VEC3","min":[0,0,0],"max":[1,1,0]},
          {"bufferView":nrm,"componentType":5126,"count":3,"type":"VEC3"},
          {"bufferView":uv,"componentType":5126,"count":3,"type":"VEC2"},
          {"bufferView":idx,"componentType":5123,"count":3,"type":"SCALAR"}]
    }
    raw=json.dumps(data,separators=(",",":")).encode()
    raw+=b" "*(-len(raw)%4)
    return (struct.pack("<III",0x46546c67,2,12+8+len(raw)+8+len(binary)) +
            struct.pack("<II",len(raw),0x4e4f534a) + raw +
            struct.pack("<II",len(binary),0x004e4942) + bytes(binary))
