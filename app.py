from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Iterable
import zipfile

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
FORMAT_TO_EXTENSION = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}
POSITION_OPTIONS = {
    "Góc dưới phải": "bottom_right",
    "Góc dưới trái": "bottom_left",
    "Góc trên phải": "top_right",
    "Góc trên trái": "top_left",
    "Chính giữa": "center",
}
RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


@dataclass
class SourceImage:
    name: str
    data: bytes
    extension: str


def inspect_image_bytes(data: bytes, source_name: str) -> str:
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            image_format = image.format
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"`{source_name}` không phải ảnh hợp lệ hoặc bị lỗi định dạng.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ValueError(
            f"`{source_name}` có định dạng không được hỗ trợ. Chỉ dùng PNG, JPG/JPEG hoặc WEBP."
        )

    return FORMAT_TO_EXTENSION[image_format]


def read_image_upload(uploaded_file) -> SourceImage:
    data = uploaded_file.getvalue()
    if not data:
        raise ValueError(f"`{uploaded_file.name}` đang trống hoặc không đọc được.")

    extension = inspect_image_bytes(data, uploaded_file.name)
    return SourceImage(name=uploaded_file.name, data=data, extension=extension)


def extract_images_from_zip(uploaded_zip) -> tuple[list[SourceImage], list[str]]:
    images: list[SourceImage] = []
    skipped_files: list[str] = []

    try:
        zip_bytes = BytesIO(uploaded_zip.getvalue())
        with zipfile.ZipFile(zip_bytes) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue

                try:
                    data = archive.read(entry)
                except OSError:
                    skipped_files.append(entry.filename)
                    continue

                try:
                    extension = inspect_image_bytes(data, entry.filename)
                except ValueError:
                    skipped_files.append(entry.filename)
                    continue

                images.append(SourceImage(name=entry.filename, data=data, extension=extension))
    except zipfile.BadZipFile as exc:
        raise ValueError("File ZIP không hợp lệ hoặc đã bị hỏng.") from exc

    if not images:
        raise ValueError("ZIP không có ảnh hợp lệ. Hãy kiểm tra lại file nén.")

    return images, skipped_files


def open_image_rgba(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as image:
        normalized = ImageOps.exif_transpose(image)
        return normalized.convert("RGBA")


def open_image_for_preview(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as image:
        normalized = ImageOps.exif_transpose(image)
        if normalized.mode in {"RGBA", "LA"}:
            return normalized.convert("RGBA")
        return normalized.convert("RGB")


def prepare_logo(
    logo_source: SourceImage,
    base_width: int,
    base_height: int,
    logo_width_percent: int,
    opacity_percent: int,
    margin: int,
    keep_transparency: bool,
) -> Image.Image:
    logo = open_image_rgba(logo_source.data)

    if not keep_transparency:
        solid_background = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        solid_background.alpha_composite(logo)
        logo = solid_background

    max_width = max(1, base_width - (margin * 2))
    max_height = max(1, base_height - (margin * 2))
    requested_width = max(1, int(base_width * (logo_width_percent / 100)))
    target_width = min(requested_width, max_width)

    scale_ratio = target_width / logo.width
    target_height = max(1, int(logo.height * scale_ratio))

    if target_height > max_height:
        scale_ratio = max_height / logo.height
        target_width = max(1, int(logo.width * scale_ratio))
        target_height = max(1, int(logo.height * scale_ratio))

    resized_logo = logo.resize((target_width, target_height), RESAMPLE)

    if opacity_percent < 100:
        alpha = resized_logo.getchannel("A")
        alpha = alpha.point(lambda value: int(value * (opacity_percent / 100)))
        resized_logo.putalpha(alpha)

    return resized_logo


def compute_logo_position(
    base_width: int,
    base_height: int,
    logo_width: int,
    logo_height: int,
    position_key: str,
    margin: int,
) -> tuple[int, int]:
    max_x = max(0, base_width - logo_width)
    max_y = max(0, base_height - logo_height)

    if position_key == "top_left":
        return min(margin, max_x), min(margin, max_y)
    if position_key == "top_right":
        return max(0, base_width - logo_width - margin), min(margin, max_y)
    if position_key == "bottom_left":
        return min(margin, max_x), max(0, base_height - logo_height - margin)
    if position_key == "center":
        return max(0, (base_width - logo_width) // 2), max(0, (base_height - logo_height) // 2)
    return max(0, base_width - logo_width - margin), max(0, base_height - logo_height - margin)


def merge_logo(
    image_source: SourceImage,
    logo_source: SourceImage,
    position_key: str,
    logo_width_percent: int,
    opacity_percent: int,
    margin: int,
    keep_transparency: bool,
) -> Image.Image:
    base_image = open_image_rgba(image_source.data)
    logo = prepare_logo(
        logo_source=logo_source,
        base_width=base_image.width,
        base_height=base_image.height,
        logo_width_percent=logo_width_percent,
        opacity_percent=opacity_percent,
        margin=margin,
        keep_transparency=keep_transparency,
    )

    pos_x, pos_y = compute_logo_position(
        base_width=base_image.width,
        base_height=base_image.height,
        logo_width=logo.width,
        logo_height=logo.height,
        position_key=position_key,
        margin=margin,
    )

    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    overlay.paste(logo, (pos_x, pos_y), logo)
    return Image.alpha_composite(base_image, overlay)


def export_image(image: Image.Image, extension: str) -> bytes:
    output = BytesIO()

    if extension in {".jpg", ".jpeg"}:
        image.convert("RGB").save(output, format="JPEG", quality=95)
    elif extension == ".webp":
        image.save(output, format="WEBP", quality=95)
    else:
        image.save(output, format="PNG", optimize=True)

    return output.getvalue()


def normalized_output_name(name: str, extension: str) -> str:
    safe_path = PurePosixPath(name.replace("\\", "/"))
    parent_parts = [part for part in safe_path.parent.parts if part not in {".", ""}]
    prefix = "_".join(parent_parts)
    stem = safe_path.stem or "image"
    base_name = f"{prefix}_{stem}" if prefix else stem
    return f"{base_name}_logo{extension}"


def make_unique_name(candidate: str, used_names: set[str]) -> str:
    path = Path(candidate)
    stem = path.stem
    suffix = path.suffix
    unique_name = candidate
    index = 1

    while unique_name in used_names:
        unique_name = f"{stem}_{index}{suffix}"
        index += 1

    used_names.add(unique_name)
    return unique_name


def build_result_zip(
    images: Iterable[SourceImage],
    logo_source: SourceImage,
    position_key: str,
    logo_width_percent: int,
    opacity_percent: int,
    margin: int,
    keep_transparency: bool,
) -> bytes:
    zip_buffer = BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_source in images:
            merged_image = merge_logo(
                image_source=image_source,
                logo_source=logo_source,
                position_key=position_key,
                logo_width_percent=logo_width_percent,
                opacity_percent=opacity_percent,
                margin=margin,
                keep_transparency=keep_transparency,
            )
            output_name = make_unique_name(
                normalized_output_name(image_source.name, image_source.extension),
                used_names,
            )
            archive.writestr(output_name, export_image(merged_image, image_source.extension))

    return zip_buffer.getvalue()


def build_state_signature(
    images: list[SourceImage],
    logo_source: SourceImage | None,
    position_key: str,
    logo_width_percent: int,
    opacity_percent: int,
    margin: int,
    keep_transparency: bool,
) -> tuple:
    image_signature = tuple((image.name, len(image.data), image.extension) for image in images)
    logo_signature = None
    if logo_source is not None:
        logo_signature = (logo_source.name, len(logo_source.data), logo_source.extension)

    return (
        image_signature,
        logo_signature,
        position_key,
        logo_width_percent,
        opacity_percent,
        margin,
        keep_transparency,
    )


def reset_download_if_needed(current_signature: tuple) -> None:
    previous_signature = st.session_state.get("result_signature")
    if previous_signature != current_signature:
        st.session_state.pop("result_zip", None)
        st.session_state.pop("result_signature", None)


def main() -> None:
    st.set_page_config(
        page_title="Ghép logo vào ảnh",
        layout="wide",
    )

    st.title("Ghép logo vào ảnh")
    st.write(
        "Tải nhiều ảnh hoặc một file ZIP chứa ảnh, sau đó tải logo để ghép hàng loạt và nhận lại "
        "một file ZIP kết quả."
    )
    st.caption("Ảnh được xử lý tạm thời trong bộ nhớ của ứng dụng, không lưu trữ lâu dài trên server.")

    with st.sidebar:
        st.header("Tải dữ liệu")
        uploaded_images = st.file_uploader(
            "Ảnh đầu vào",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            help="Bạn có thể chọn nhiều ảnh cùng lúc.",
        )
        uploaded_zip = st.file_uploader(
            "Hoặc tải file ZIP chứa nhiều ảnh",
            type=["zip"],
            accept_multiple_files=False,
        )
        uploaded_logo = st.file_uploader(
            "Logo",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
        )

        st.header("Tùy chọn ghép logo")
        position_label = st.selectbox("Vị trí logo", list(POSITION_OPTIONS.keys()))
        logo_width_percent = st.slider("Kích thước logo (% chiều rộng ảnh)", 5, 40, 18)
        opacity_percent = st.slider("Độ mờ logo (%)", 10, 100, 75)
        margin = st.slider("Margin (pixel)", 0, 200, 24)
        keep_transparency = st.checkbox(
            "Giữ nền trong suốt của logo (nếu có)",
            value=True,
        )

    source_images: list[SourceImage] = []
    zip_skipped_files: list[str] = []
    input_errors: list[str] = []

    if uploaded_images:
        for uploaded_file in uploaded_images:
            try:
                source_images.append(read_image_upload(uploaded_file))
            except ValueError as exc:
                input_errors.append(str(exc))

    if uploaded_zip is not None:
        try:
            zip_images, zip_skipped_files = extract_images_from_zip(uploaded_zip)
            source_images.extend(zip_images)
        except ValueError as exc:
            input_errors.append(str(exc))

    logo_source: SourceImage | None = None
    if uploaded_logo is not None:
        try:
            logo_source = read_image_upload(uploaded_logo)
        except ValueError as exc:
            input_errors.append(str(exc))

    current_signature = build_state_signature(
        images=source_images,
        logo_source=logo_source,
        position_key=POSITION_OPTIONS[position_label],
        logo_width_percent=logo_width_percent,
        opacity_percent=opacity_percent,
        margin=margin,
        keep_transparency=keep_transparency,
    )
    reset_download_if_needed(current_signature)

    if input_errors:
        for message in input_errors:
            st.error(message)

    if zip_skipped_files:
        st.warning(
            f"Đã bỏ qua {len(zip_skipped_files)} file trong ZIP vì không phải ảnh hợp lệ hoặc lỗi định dạng."
        )

    if source_images:
        st.success(f"Đã nhận {len(source_images)} ảnh hợp lệ để xử lý.")
    else:
        st.info("Hãy tải nhiều ảnh trực tiếp hoặc một file ZIP chứa ảnh.")

    preview_col, action_col = st.columns([2, 1], gap="large")

    with preview_col:
        st.subheader("Preview")
        if source_images and logo_source is not None:
            try:
                preview_original = open_image_for_preview(source_images[0].data)
                preview_merged = merge_logo(
                    image_source=source_images[0],
                    logo_source=logo_source,
                    position_key=POSITION_OPTIONS[position_label],
                    logo_width_percent=logo_width_percent,
                    opacity_percent=opacity_percent,
                    margin=margin,
                    keep_transparency=keep_transparency,
                )

                original_col, merged_col = st.columns(2)
                with original_col:
                    st.image(
                        preview_original,
                        caption=f"Ảnh gốc: {Path(source_images[0].name).name}",
                        use_container_width=True,
                    )
                with merged_col:
                    st.image(
                        preview_merged,
                        caption="Ảnh sau khi ghép logo",
                        use_container_width=True,
                    )
            except ValueError as exc:
                st.error(str(exc))
        else:
            st.info("Preview sẽ hiện sau khi bạn tải ít nhất một ảnh hợp lệ và một logo.")

    with action_col:
        st.subheader("Xuất kết quả")
        st.write("Kết quả sẽ được gom thành một file ZIP để tải về.")

        if st.button("Ghép logo và tải xuống", type="primary", use_container_width=True):
            if not source_images:
                st.error("Vui lòng tải lên ít nhất một ảnh hoặc một file ZIP chứa ảnh hợp lệ.")
            elif logo_source is None:
                st.error("Vui lòng tải lên logo hợp lệ trước khi xử lý.")
            else:
                try:
                    result_zip = build_result_zip(
                        images=source_images,
                        logo_source=logo_source,
                        position_key=POSITION_OPTIONS[position_label],
                        logo_width_percent=logo_width_percent,
                        opacity_percent=opacity_percent,
                        margin=margin,
                        keep_transparency=keep_transparency,
                    )
                    st.session_state["result_zip"] = result_zip
                    st.session_state["result_signature"] = current_signature
                    st.success(f"Đã ghép logo cho {len(source_images)} ảnh.")
                except ValueError as exc:
                    st.error(str(exc))

        if st.session_state.get("result_zip"):
            st.download_button(
                label="Tải file ZIP kết quả",
                data=st.session_state["result_zip"],
                file_name="anh_da_ghep_logo.zip",
                mime="application/zip",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
