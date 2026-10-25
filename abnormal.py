from sys import argv, exit
from pathlib import Path
from collections import namedtuple
import traceback
from json import loads, JSONDecodeError
from math import sqrt

def error(text):
    print("An error occoured:")
    print(text)
    print("Press enter to close.")
    input()
    exit()

try:
    from PIL import Image
except ModuleNotFoundError:
    error("Pillow is required. Install by running this in the terminal: py -m pip install Pillow")

def detect_nrm_type(nrm_image:Image.Image) -> Nrm_type:
    """
    Tries to detect normal map type by checking image
    against medium values given in nrm_types and also
    always-expected values coming from unused channels.

    Will not detect DirectX or BRDF because they aren't
    easily detectable.
    """
    nrm_image = nrm_image.resize((64,64))
    nrm_pixels = nrm_image.load()

    avrg_color_scores = {}

    for nrm_type in nrm_types:
        avrg_color_scores[nrm_type] = []

    blues = []

    for x in range(64):
      for y in range(64):
        #print()
        current_pixel = nrm_pixels[x,y]
        blues.append(current_pixel[2])

        for nrm_type in nrm_types:
        # for each nrm type
            if nrm_type.avrg_color is None:
                avrg_color_scores[nrm_type].append(0)
                continue

            current_scores_expected = []
            current_scores_always_expected = []

            if nrm_type.code == 'xyz_' and current_pixel == (0,0,0,0):
                continue #opengl normal maps sometimes have 0,0,0,0 pixels outside uv boundries and we don't want those to affect calculation

            for i, (expected, always_expected) in enumerate(zip(nrm_type.avrg_color,nrm_type.always_color)):
            # for each channel

                if always_expected is not None:
                    #check if always-expected value matches or not. always-expected has more weight and is more strict.
                    if round(current_pixel[i]/6) == round(always_expected/6):
                        current_scores_always_expected.append(255)
                    else:
                        current_scores_always_expected.append(0)
                    continue

                if expected is None:
                    continue

                current_scores_expected.append(255 - abs(current_pixel[i] - expected))

            #print(current_scores_expected,current_scores_always_expected,nrm_type.display_name)
            current_avarage = sum(current_scores_expected)/len(current_scores_expected)
            current_avarage = (current_avarage+sum(current_scores_always_expected)) / (len(current_scores_always_expected)+1)

            avrg_color_scores[nrm_type].append(current_avarage)

    for name,scores in avrg_color_scores.items():

        avrg_color_scores[name] = sum(scores)/len(scores) #because sometimes we skip adding scores
        #print(name, sum(scores)/len(scores))

    winners = sorted(avrg_color_scores.items(), key=lambda a: a[1], reverse=True)

    winner = winners[0][0]

    # common mistake: sees two-channel as rxgb 255, so check only blue channel again

    #print(winners[0][0].code, winners[1][0].code, sum(blues)/64)

    if (winners[0][0].code=='_yzx' and
        winners[1][0].code=='_y_x' and
        sum(blues)/64/64 >254):

        winner = winners[1][0]

    #print('winner:', winner )
    return winner

def convert_nrm_type(
        nrm_image_orig:Image.Image,
        src_type:Nrm_type,
        out_type:Nrm_type,
        brdf_image:Image.Image,
        brdf_filename:str
    ) -> Image.Image:
    nrm_pixels_orig = nrm_image_orig.load()
    width, height = nrm_image_orig.size
    nrm_image_new:Image.Image = Image.new("RGBA", (width,height))
    nrm_pixels_new = nrm_image_new.load()

    brdf_pixels = None
    if (
        brdf_image is not None and
        "r" not in src_type.code and
        "r" in out_type.code
    ):
        brdf_pixels = brdf_image.load()
        print(f"Using {brdf_filename} for roughness")

    prev_rgba = None

    cached = {} #orig_rgba255: new_rgba255
    
    for img_x in range(width):
      for img_y in range(height):

        rgba_255 = nrm_pixels_orig[img_x,img_y]

        brdf_roughness_255 = 0
        if brdf_pixels is not None:
            brdf_roughness_255 = brdf_pixels[img_x,img_y][1]

        if (rgba_255,brdf_roughness_255) in cached:
            nrm_pixels_new[img_x,img_y] = cached[(rgba_255,brdf_roughness_255)]
            continue

        rgba_float = [c /255 *2 -1 for c in rgba_255] #-1 to 1

        x=y=z= r= dx=dy= None

        brdf_roughness = brdf_roughness_255/255 *2 -1

        # ======= to x,y,z,r =======

        for idx, nrm_val in enumerate(src_type.code):

            current_channel = rgba_float[idx]

            if nrm_val == "x":
                x = current_channel
                
            elif nrm_val =="y":
                y = current_channel
            elif nrm_val =="z":
                z = current_channel

            elif nrm_val =="Y":
                y = -current_channel
            elif nrm_val =="Z":
                z = current_channel+1 #normally ranged 0 to 1, here ranged -1 to 0
                z = z if z<=1 else 1

            elif nrm_val =="r":
                r = current_channel #current_channel is normally ranged from -1 to 1, this shouldn't matter as all we're doing with the roughness channel is copying it

            elif nrm_val =="d":
                dx = current_channel
            elif nrm_val =="D":
                dy = current_channel

        # ======= to nrm image =======

        rgba_float = [0,0,0,0]

        if "x" in out_type.code and x is None and dx is not None:
            nrm_length = sqrt(dx**2 + dy**2 + 1)
            if round(nrm_length)!=0:
                x, y, z = -dx/nrm_length, -dy/nrm_length, 1/nrm_length
            else:
                x, y, z = 0, 0, 1

        if "d" in out_type.code and dx is None and x is not None:
            dx = -x/z if round(z)!=0 else 0
            dy = -y/z if round(z)!=0 else 0

        if "z" in out_type.code and z is None and x is not None:
            z = sqrt(1 - x**2 - y**2)

        if "x" in out_type.code and x is None:
            x,y,z = 0,0,1

        if "r" in out_type.code and r is None and brdf_roughness is not None:
            r = brdf_roughness
        
        for idx, nrm_val in enumerate(out_type.code):
            if nrm_val == "x":
                rgba_float[idx] = x
            elif nrm_val =="y":
                rgba_float[idx] = y
            elif nrm_val =="z":
                rgba_float[idx] = z

            elif nrm_val =="Y":
                rgba_float[idx] = -y
            elif nrm_val =="Z":
                rgba_float[idx] = z-1 if z-1>=0 else 0

            elif nrm_val =="r":
                rgba_float[idx] = r

            elif nrm_val =="d":
                rgba_float[idx] = dx
            elif nrm_val =="D":
                rgba_float[idx] = dy

            elif nrm_val == "_":
                rgba_float[idx] = 1

            elif nrm_val == "-":
                rgba_float[idx] = -1

        rgba_255_new = tuple(round((c+1)/2*255) for c in rgba_float)
        cached[(rgba_255,brdf_roughness_255)] = rgba_255_new

        nrm_pixels_new[img_x,img_y] = rgba_255_new

    return nrm_image_new
        
def main():
    try:
        nrm_path = argv[1]
    except IndexError:
        nrm_path = input("Drag your image to this window to append the path, then press enter:\n").replace('"',"")
        print()

    nrm_file = Path(nrm_path)
    # backup_nrm_file = Path(nrm_path+".bak")

    # try:
    #     backup_nrm_file.write_bytes(
    #         nrm_file.read_bytes()
    #     )
    # except FileNotFoundError:
    #     error("Path is invalid.")

    try:
        nrm_image = Image.open(nrm_file).convert('RGBA')
    except FileNotFoundError:
        error("File was not found.")
    except IOError:
        error("Image can't be opened, likely invalid.")

    brdf_image = brdf_filename= None

    brdf_files = tuple(nrm_file.parent.glob(f"{nrm_file.stem}_brdf.*",case_sensitive=False))

    if not brdf_files:
        brdf_files = tuple(nrm_file.parent.glob(
            f"{nrm_file.stem.lower()
            .replace("_dx11","_brdf_dx11")
            .replace("_nxg","_brdf_nxg")
            }.*",case_sensitive=False
        ))
        brdf_files = [a for a in brdf_files if a!=nrm_file]

    if not brdf_files:
        brdf_files = tuple(nrm_file.parent.glob(
            f"{nrm_file.stem.lower()
            .replace("_normal","_brdf")
            .replace("_norm","_brdf")
            .replace("_nrmr","_brdf")
            .replace("_nrm","_brdf")
            .replace("_nm","_brdf")
            }.*",case_sensitive=False
        ))
        brdf_files = [a for a in brdf_files if a!=nrm_file]

    if brdf_files:
        brdf_files_matching_ext = [
            f for f in brdf_files
            if f.suffix.lower() == nrm_file.suffix.lower()
        ]

        if brdf_files_matching_ext:
            brdf_file = brdf_files_matching_ext[0]

        else:
            brdf_file = brdf_files[0]

        brdf_filename = brdf_file.name
        
        try:
            brdf_image = Image.open(brdf_file).convert('RGBA')
        except IOError:
            pass
        else:
            if brdf_image.size != nrm_image.size:
                brdf_image = brdf_image.resize(nrm_image.size)

    global Nrm_type
    Nrm_type = namedtuple("Nrm_type",(
        "display_name", "avrg_color","always_color","code"
    ))

    global nrm_types
    nrm_types = (
        Nrm_type('OpenGL',        (128,128,255,None),    (None,None,None,255),   "xyz_"), #purple
        Nrm_type('OpenGL-R',      (128,128,255,None),    (None,None,None,None),  "xyzr"), #trans-purple
        Nrm_type('DirectX',       None,                  (None,None,None,None),  "xYz_"), #purple
        Nrm_type('RXGB',          (None,128,255,128),    (255,None,None,None),   "_yzx"), #trans-pink
        Nrm_type('RXGB-R',        (None,128,255,128),    (None,None,None,None),  "ryzx"), #trans-blue
        Nrm_type('B128',          (128,128,128,None),    (None,None,None,255),   "xyZ_"), #gray
        Nrm_type('RXGB-B128-R',   (None,128,128,128),    (None,None,None,None),  "ryZx"), #trans-teal - trans-pink
        Nrm_type('TwoChannel-R',  (None,128,None,128),   (None,None,255,None),   "_y_x"), #trans-pink
        Nrm_type('Derivative',    (128,128,None,None),   (None,None,0,255),      "dD-_"), #green
        Nrm_type('BRDF',          None,                  (None,None,None,None),  "_r__"), #any
    )

    detected_nrm_type = detect_nrm_type(nrm_image)

    nrm_types_toprint = ''

    for id,nrm_type in enumerate(nrm_types,start=1):

        if nrm_type == detected_nrm_type:
            nrm_types_toprint += f'[{id}] {nrm_type.display_name} ***\n'
        else:
            nrm_types_toprint += f'[{id}] {nrm_type.display_name}\n'

    
    print(
        f"Normal map type detected as **{detected_nrm_type.display_name}** ."
        "\nIf this is correct, type just the ID for the output nrm type.\n"
        'Otherwise type the input ID and the output ID (so "1, 5" for '
        "OpenGL to RXGB-R). Then press enter.\n"
    )

    print(nrm_types_toprint.strip())

    error_msg = "Invalid response. Please enter a valid response."

    while True:

        try:
            response = loads(f"[{input("> ")}]")
        except JSONDecodeError:
            print(error_msg)
            continue

        if len(response) == 1:
            try:
                src_nrm_type = detected_nrm_type
                out_nrm_type = nrm_types[int(response[0])-1]
            except IndexError, ValueError, TypeError:
                print(error_msg)
                continue

        else:
            try:
                src_nrm_type = nrm_types[int(response[0])-1]
                out_nrm_type = nrm_types[int(response[1])-1]
            except IndexError, ValueError, TypeError:
                print(error_msg)
                continue

        ## let's not be annoying
        # if src_nrm_type == out_nrm_type:
        #     print("Can't convert to source nrm type. Please enter another output nrm type.")
        #     continue

        break

    print("Conversion started. Please wait...")
    converted_nrm_image = convert_nrm_type(
        nrm_image,
        src_nrm_type,
        out_nrm_type,
        brdf_image,
        brdf_filename,
    )

    output_nrm_file = nrm_file.parent / (nrm_file.stem + "_new_" + out_nrm_type.display_name + ".png")
    
    converted_nrm_image.save(output_nrm_file)
    print("Saved.")

try:
    main()
except:
    print("An unknown error occoured:")
    traceback.print_exc()
print("Press enter to close.")
input()
exit()