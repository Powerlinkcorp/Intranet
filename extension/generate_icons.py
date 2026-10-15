import os
import struct
import zlib
import math

def create_png_icon(size, filename):
    width = size
    height = size
    # BG: Brand blue #2563eb (37, 99, 235) with rounded corners and white inner shape
    raw = bytearray()
    radius = size * 0.22
    cx, cy = size / 2, size / 2
    
    for y in range(height):
        raw.append(0) # filter type 0
        for x in range(width):
            # Rounded rect distance
            dx = max(abs(x - cx) - (cx - radius), 0)
            dy = max(abs(y - cy) - (cy - radius), 0)
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist <= radius:
                # Inside rounded container
                # Let's draw an inner white shield/plus icon
                nx = (x - cx) / (size * 0.35)
                ny = (y - cy) / (size * 0.35)
                
                # Check if in plus or symbol area
                is_symbol = (abs(nx) < 0.28 and abs(ny) < 0.8) or (abs(ny) < 0.28 and abs(nx) < 0.8)
                
                if is_symbol:
                    # White icon
                    raw.extend([255, 255, 255, 255])
                else:
                    # Blue gradient
                    gradient_factor = 1.0 - (y / height) * 0.25
                    r = int(37 * gradient_factor)
                    g = int(99 * gradient_factor)
                    b = int(235 * gradient_factor)
                    raw.extend([r, g, b, 255])
            else:
                # Transparent outside
                raw.extend([0, 0, 0, 0])

    # PNG structure with RGBA (color type 6)
    png = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = struct.pack('>I', zlib.crc32(b'IHDR' + ihdr))
    png += struct.pack('>I', len(ihdr)) + b'IHDR' + ihdr + ihdr_crc
    
    compressed = zlib.compress(bytes(raw), level=9)
    idat_crc = struct.pack('>I', zlib.crc32(b'IDAT' + compressed))
    png += struct.pack('>I', len(compressed)) + b'IDAT' + compressed + idat_crc
    
    iend_crc = struct.pack('>I', zlib.crc32(b'IEND'))
    png += struct.pack('>I', 0) + b'IEND' + iend_crc
    
    with open(filename, 'wb') as f:
        f.write(png)

icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
os.makedirs(icons_dir, exist_ok=True)

for s in [16, 32, 48, 128]:
    path = os.path.join(icons_dir, f'icon{s}.png')
    create_png_icon(s, path)
    print(f"Generado: {path} ({s}x{s})")
