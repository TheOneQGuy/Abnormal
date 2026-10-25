# Abnormal
Python script to convert a normal map image into different custom normal map types used in TT Lego games. Used to be AI-generated but I rewrote it from scratch myself without AI. The provided py file (written in Python 3.14 and should work with versions around that time) is recommended but the exe found in the releases section can also be used for people who can't get the py file to work properly (or people who want to use the script via right click and `Open with`). Pillow is required if you are using the py file.

Now console based instead of having an unnecessary GUI.

Use by dragging an image file with a supported format onto the script. It will try to automatically detect the normal map type (and usually gets it right). Note that it will not detect DirectX or BRDF as those are hard to detect. 10 normal map types are supported:

| Name  | Visual color | Supports normals? | Supports roughness? | Common era |
|-------|-----|-------|-|-|
|OpenGL | Purple|Yes | No | All|
|OpenGL-R | Trans-purple|Yes | Yes | NXG|
|DirectX | Purple|Yes | No | UE5
|RXGB | Trans-pink|Yes | No | Classic
|RXGB-R | Trans-blue - Trans-pink|Yes | Yes | NXG, DX11
|B128 |Gray| Yes | No | NXG, DX11
|RXGB-B128-R |Trans-teal - Trans-pink| Yes | Yes | NXG, DX11
|TwoChannel-R | Trans-pink|Yes | Unknown (No)| NXG, DX11
|Derivative | Green|Yes | Unknown (No)| NTT
|BRDF | Pink (usually) | No | Yes | NXG, DX11, NTT

This image shows the same normal map converted to each type (in order):

<img width="5120" height="2048" alt="image" src="https://github.com/user-attachments/assets/7c6ae77e-c158-4d62-9bd8-e4bd58cf1203" />


You can usually rely on the automatic detection and only type the ID for the type you want to convert to. In cases where the detection is wrong, type both the input and output type (e.g. `3, 6` for DirectX to B128).

The output image is saved with this filename: {original path and name}\_new_{nrm type}.png

Note that the script only exports as png, and need to convert it to a DDS yourself to use it in a game.

As you can see, some normal map types also support a roughness channel, which is sometimes used for models that don't have BRDF images. Abnormal keeps the roughness channel when converting between normal map types that have roughness. When you want to extract only roughness information, you can choose to convert to a BRDF texture with the G channel used.

You may want to mix a BRDF texture's roughness and a non-roughness normal map type into a normal map type that allows roughness. To do this, have the BRDF texture in the same folder as the normal map texture, and drag the normal map onto Abnormal. If the input normal map does not have a roughness channel but the output channel does, Abnormal will try to find the corresponding BRDF texture with the same name as the normal map but with `_BRDF` (case insensitive) appended at the end. If it finds a valid image with a matching name, it will automatically use that image. Otherwise, a default roughness value of 0 is used, which is consistent with models that use normal map types that technically have a roughness channel but the model doesn't use it.
