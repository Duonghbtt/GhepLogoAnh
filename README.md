# Ghép logo vào ảnh

Ứng dụng web viết bằng Streamlit để ghép một logo vào nhiều ảnh cùng lúc. Người dùng có thể tải nhiều ảnh trực tiếp hoặc tải một file ZIP chứa ảnh, chọn vị trí và độ mờ logo, xem preview ảnh đầu tiên rồi tải về một file ZIP chứa toàn bộ ảnh đã được ghép logo.

## Tính năng chính

- Upload nhiều ảnh `png`, `jpg`, `jpeg`, `webp`.
- Hoặc upload một file `.zip` chứa nhiều ảnh.
- Upload logo `png`, `jpg`, `jpeg`, `webp`.
- Tùy chỉnh vị trí, kích thước theo `%` chiều rộng ảnh, độ mờ và margin.
- Hỗ trợ giữ nền trong suốt của logo nếu logo có kênh alpha.
- Bỏ qua file không phải ảnh trong ZIP.
- Xử lý hoàn toàn trong bộ nhớ để phù hợp deploy trên Streamlit Community Cloud.
- Xuất kết quả thành file ZIP để người dùng tải về.

## Chạy local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy lên Streamlit Community Cloud

1. Tạo GitHub repo.
2. Upload các file `app.py`, `requirements.txt`, `README.md`, `.streamlit/config.toml`.
3. Vào Streamlit Community Cloud.
4. Chọn repo, branch, file chính là `app.py`.
5. Deploy và copy link gửi cho người khác.

## Cấu trúc project

```text
.
|-- app.py
|-- requirements.txt
|-- README.md
|-- .gitignore
`-- .streamlit/
    `-- config.toml
```
