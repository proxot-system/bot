import asyncio
import concurrent.futures
import math
import os
import sys
from pathlib import Path

from pyvips import Image


async def get_image(source: str):
	from utilities.misc import fetch

	if source.startswith(("http://", "https://")):
		image_bytes = await fetch(source, output="read")
		return Image.new_from_buffer(image_bytes, "")
	elif Path(source).exists():
		return Image.new_from_file(str(Path(source)))
	else:
		raise FileNotFoundError(f"Source not found: {source}")


def create_blur_kernel(length, angle_rad):
	if length < 2:
		return None

	size = int(length * 2) + 1
	kernel = Image.black(size, size, bands=1)

	cx, cy = size // 2, size // 2
	ex = cx + int(math.cos(angle_rad + math.pi) * length)
	ey = cy + int(math.sin(angle_rad) * length)

	kernel = kernel.draw_line([1.0], cx, cy, ex, ey)

	total_sum = kernel.avg() * kernel.width * kernel.height
	return kernel / total_sum


def render_chunk_to_canvas(
	chunk_id, chunk, tile, canvas_w, canvas_h, max_dist, blur_intensity, batch_size, darkening_intensity
):
	layer = Image.black(canvas_w, canvas_h, bands=4).copy(interpretation="srgb")

	images, xs, ys, modes = [], [], [], []
	kernel_cache = {}

	total = len(chunk)
	total_list[chunk_id] = total

	for idx, (fx, fy, dist, angle) in enumerate(chunk):
		if idx % 5 == 0:
			progress_list[chunk_id] = idx

		brightness = max(0.2, 1.0 - (dist / (max_dist * darkening_intensity)))
		flower = tile.linear([brightness, brightness, brightness, 1.0], [0, 0, 0, 0])

		final_fx, final_fy = fx, fy

		if dist > 1.0:
			blur_len = int(dist * blur_intensity)
			q_angle = round(angle / (math.pi / 12)) * (math.pi / 12)
			if blur_len > 1:
				flower = flower.embed(blur_len, blur_len, flower.width + blur_len * 2, flower.height + blur_len * 2)
				final_fx -= blur_len
				final_fy -= blur_len
				cache_key = (blur_len, q_angle)
				if cache_key not in kernel_cache:
					kernel_cache[cache_key] = create_blur_kernel(blur_len, q_angle)
				kernel = kernel_cache[cache_key]
				if kernel:
					flower = flower.conv(kernel)
		baked_flower = flower.copy_memory()
		images.append(baked_flower)
		xs.append(round(final_fx))
		ys.append(round(final_fy))
		modes.append("over")

		if len(images) >= batch_size:
			layer = layer.composite(images, modes, x=xs, y=ys).copy_memory()
			images, xs, ys, modes = [], [], [], []

	if images:
		layer = layer.composite(images, modes, x=xs, y=ys).copy_memory()
	progress_list[chunk_id] = total
	return layer


async def report_progress(num_threads):
	sys.stdout.write("\n" * num_threads)
	sys.stdout.flush()
	while True:
		sys.stdout.write(f"\033[{num_threads}A")
		for i in range(num_threads):
			p, t = progress_list[i], total_list[i]
			pct = (p / t * 100) if t > 0 else 0
			sys.stdout.write(f"Thread {i}: {p}/{t} ({pct:.1f}%)\033[K\n")
		sys.stdout.flush()
		if all(p == t and t > 0 for p, t in zip(progress_list, total_list)):
			break
		await asyncio.sleep(0.1)


def run():
	import asyncio

	asyncio.run(render_banner())


async def render_banner():
	step_x_col, step_x_row = 6, 2
	step_y_alt = 2
	step_y_row = -7

	canvas_w, canvas_h = 85, 30
	blur_intensity = 0.1
	batch_size = 300
	darkening_intensity = 999

	tile_path = Path("src/data/images/other/proxot_logo_clear.png").resolve()
	tile = Image.new_from_file(str(tile_path))
	tw, th = tile.width, tile.height

	cols_range = int((canvas_w / step_x_col) * 1.5)
	rows_range = int((canvas_h / abs(step_y_row)) * 1.5)

	raw_flowers = []
	for r in range(-rows_range, rows_range):
		for c in range(-cols_range, cols_range):
			x = (c * step_x_col) + (r * step_x_row)
			y = (r * step_y_row) + ((c % 2) * step_y_alt)
			raw_flowers.append((x, y))

	target_cx = 13 - (tw / 2)
	target_cy = canvas_h - 20 - (th / 2)

	best_fit = min(raw_flowers, key=lambda f: math.sqrt((f[0] - target_cx) ** 2 + (f[1] - target_cy) ** 2))
	shift_x, shift_y = target_cx - best_fit[0], target_cy - best_fit[1]

	flowers_to_process = []
	for fx, fy in raw_flowers:
		nx, ny = fx + shift_x, fy + shift_y
		if -300 <= nx <= canvas_w + 300 and -300 <= ny <= canvas_h + 300:
			dist = math.sqrt((nx - target_cx) ** 2 + (ny - target_cy) ** 2)
			angle = math.atan2(ny - target_cy, nx - target_cx)
			flowers_to_process.append((nx, ny, dist, angle))

	flowers_to_process.sort(key=lambda f: f[2], reverse=True)

	max_dist = math.sqrt((canvas_w / 2) ** 2 + (canvas_h / 2) ** 2)
	num_threads = min(os.cpu_count() or 4, 8)
	global progress_list, total_list
	progress_list, total_list = [0] * num_threads, [0] * num_threads

	chunk_size = math.ceil(len(flowers_to_process) / num_threads)
	chunks = [flowers_to_process[i : i + chunk_size] for i in range(0, len(flowers_to_process), chunk_size)]

	loop = asyncio.get_running_loop()
	with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
		reporter = asyncio.create_task(report_progress(num_threads))
		tasks = [
			loop.run_in_executor(
				pool,
				render_chunk_to_canvas,
				i,
				chunk,
				tile,
				canvas_w,
				canvas_h,
				max_dist,
				blur_intensity,
				batch_size,
				darkening_intensity,
			)
			for i, chunk in enumerate(chunks)
		]
		layer_results = await asyncio.gather(*tasks)
		await reporter

	print("\rMerging layers...\033[K", flush=True)
	final_canvas = Image.black(canvas_w, canvas_h, bands=4).copy(interpretation="srgb")
	for layer_img in layer_results:
		final_canvas = final_canvas.composite(layer_img, "over", x=0, y=0)

	output_path = Path("ignored/tiled_canvas_result.png")
	output_path.parent.mkdir(exist_ok=True)
	final_canvas.write_to_file(str(output_path))
	print("Done! Image saved as tiled_canvas_result.png", flush=True)
