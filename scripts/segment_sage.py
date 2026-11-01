import numpy as np
from PIL import Image

def build_sage_master():
    # 1. Load image
    src_path = "assets/logo/sage_logo.png"
    im = Image.open(src_path).convert("RGBA")
    arr = np.array(im)

    # Clean borders (1-pixel artifact)
    arr[0, :] = 0
    arr[-1, :] = 0
    arr[:, 0] = 0
    arr[:, -1] = 0

    # 2. Extract channels
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)

    # Max intensity per pixel
    v = np.maximum(np.maximum(r, g), b)

    # 3. Create spatial mask for the man alone (removing background constellation lines)
    # The constellation on the left is in:
    # Y in [0, 360], X < 430
    # Y in [360, 440], X < 380 - (Y - 360)*0.7  (contour of the left bicep/elbow)
    # The left hand mudra starts at Y >= 440, X >= 315
    mask_keep = np.ones((arr.shape[0], arr.shape[1]), dtype=bool)

    # Left constellation cut
    for y in range(arr.shape[0]):
        if y < 220:
            # Above shoulder: man is at X >= 490
            mask_keep[y, :490] = False
        elif y < 350:
            # Back/shoulder: man is at X >= 430
            mask_keep[y, :430] = False
        elif y < 440:
            # Upper arm / elbow slope from X=430 at 350 to X=375 at 400 to X=350 at 440
            t = (y - 350) / 90.0
            boundary_x = int(430 * (1 - t) + 350 * t)
            mask_keep[y, :boundary_x] = False
        elif y < 530:
            # Left hand mudra & forearm: man is at X >= 315
            mask_keep[y, :315] = False
        else:
            # Crossed legs: man is at X >= 330
            mask_keep[y, :330] = False

    # Right constellation cut (under the outstretched arm / sleeve, above lap)
    # The hollow area is between Y in [330, 470], X in [685, 800]
    # In this hollow space, the constellation nodes are at X > 690, Y between bottom of sleeve and top of lap
    for y in range(330, 475):
        for x in range(680, 800):
            # Check if this pixel is inside the sleeve or lap:
            # The sleeve is at Y <= 360 or (Y in 360..390 with X > 780)
            # The lap is at Y >= 465 (rising on the right knee to Y=450 at X=780)
            is_sleeve = (y <= 355) or (x >= 790 and y <= 380)
            is_lap = (y >= 475) or (x >= 760 and y >= 455) or (x < 700 and y >= 440)
            if not is_sleeve and not is_lap:
                mask_keep[y, x] = False

    # Also, anything above the head (Y < 30) or below the feet (Y > 650) is background
    mask_keep[:30, :] = False
    mask_keep[650:, :] = False

    # 4. Compute alpha channel
    # Clean background noise (v < 14 -> 0)
    # Smooth ramp from 14 to 32, linear above 32
    alpha = np.zeros_like(v)
    valid_pts = mask_keep & (v >= 14)
    ramp_pts = valid_pts & (v < 32)
    linear_pts = valid_pts & (v >= 32)

    alpha[ramp_pts] = (v[ramp_pts] - 14.0) / (32.0 - 14.0) * 32.0
    alpha[linear_pts] = v[linear_pts]

    # Tilak enhancement: keep red mark fully opaque and saturated
    is_tilak = (r > 140) & (g < 90) & (b < 90) & (arr.shape[0] > 70)
    alpha[is_tilak] = 255.0

    # Ensure range [0, 255]
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    # 5. Form RGBA image
    out_arr = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
    out_arr[:, :, 0] = arr[:, :, 0]
    out_arr[:, :, 1] = arr[:, :, 1]
    out_arr[:, :, 2] = arr[:, :, 2]
    out_arr[:, :, 3] = alpha

    # 6. Tightly crop to bounding box of non-zero alpha
    non_zero = np.where(alpha > 0)
    y_min, y_max = non_zero[0].min(), non_zero[0].max()
    x_min, x_max = non_zero[1].min(), non_zero[1].max()

    cropped_arr = out_arr[y_min:y_max+1, x_min:x_max+1]
    master = Image.fromarray(cropped_arr, mode="RGBA")

    # Assertions required by prompt
    assert master.mode == "RGBA", f"Expected RGBA mode, got {master.mode}"
    extrema = master.getchannel("A").getextrema()
    assert extrema != (255, 255), f"Expected transparent pixels, got extrema {extrema}"
    assert extrema[0] == 0, f"Expected minimum alpha 0, got {extrema[0]}"
    assert extrema[1] > 200, f"Expected maximum alpha > 200, got {extrema[1]}"

    master.save("assets/logo/sage_master.png")
    print(f"[SUCCESS] Saved assets/logo/sage_master.png: size={master.size}, alpha_extrema={extrema}")
    return master

if __name__ == "__main__":
    build_sage_master()
