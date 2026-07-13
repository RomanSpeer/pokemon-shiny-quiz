import os
from moviepy.editor import ColorClip, CompositeVideoClip

# TikTok vertical video resolution (1080×1920) – you can adjust if needed
WIDTH, HEIGHT = 1080, 1920
DURATION = 10  # seconds

def create_quadrant_video(output_path: str = "output.mp4"):
    """Create a 10‑second video with the screen divided into four colored quadrants.

    The video is saved to ``output_path``.
    """
    # Define the size of each quadrant (half the width and half the height)
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2

    # Create four solid‑color clips – you can change the RGB values as desired
    top_left = ColorClip(size=(quad_w, quad_h), color=(255, 0, 0)).set_duration(DURATION)   # red
    top_right = ColorClip(size=(quad_w, quad_h), color=(0, 255, 0)).set_duration(DURATION)  # green
    bottom_left = ColorClip(size=(quad_w, quad_h), color=(0, 0, 255)).set_duration(DURATION)  # blue
    bottom_right = ColorClip(size=(quad_w, quad_h), color=(255, 255, 0)).set_duration(DURATION)  # yellow

    # Position each quadrant within the full‑size canvas
    top_left = top_left.set_position((0, 0))
    top_right = top_right.set_position((quad_w, 0))
    bottom_left = bottom_left.set_position((0, quad_h))
    bottom_right = bottom_right.set_position((quad_w, quad_h))

    # Composite the four quadrants onto a background canvas
    final_clip = CompositeVideoClip([
        top_left,
        top_right,
        bottom_left,
        bottom_right,
    ], size=(WIDTH, HEIGHT)).set_duration(DURATION)

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Write the video file – using a common codec for compatibility
    final_clip.write_videofile(output_path, fps=30, codec="libx264", audio=False)

if __name__ == "__main__":
    create_quadrant_video()
