"""Bake a linear vertex-color surface to a non-overlapping padded UV atlas."""
from io import BytesIO
import math
import numpy as np
from PIL import Image

def bake_faces(faces, linear_rgb):
    # Four interior texels plus border. Each triangle interpolates the source
    # corner colors. Duplicating seam vertices keeps joints and normals exact.
    pitch = 8
    columns = math.ceil(math.sqrt(len(faces)))
    rows = math.ceil(len(faces) / columns)
    width, height = pitch * columns, pitch * rows
    tile_x = np.arange(len(faces)) % columns * pitch
    tile_y = np.arange(len(faces)) // columns * pitch
    uv = np.empty((len(faces), 3, 2), dtype='<f4')
    for j, (x,y) in enumerate(((1,1),(5,1),(1,5))):
        uv[:,j,0] = (tile_x+x+.5)/width
        uv[:,j,1] = (tile_y+y+.5)/height
    colors = linear_rgb[faces]
    pixels = np.zeros((height,width,3),dtype=np.uint8)
    for y in range(pitch):
        for x in range(pitch):
            u,v = np.clip([(x-1)/4,(y-1)/4],0,1)
            if u+v>1: u,v = u/(u+v),v/(u+v)
            linear = colors[:,0]*(1-u-v)+colors[:,1]*u+colors[:,2]*v
            srgb = np.where(linear<=.0031308,12.92*linear,1.055*linear**(1/2.4)-.055)
            pixels[tile_y+y,tile_x+x] = np.rint(np.clip(srgb,0,1)*255)
    stream = BytesIO()
    Image.fromarray(pixels).save(stream,format='PNG')
    return uv.reshape(-1,2),stream.getvalue()
