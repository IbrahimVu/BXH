# Bảng xếp hạng thưởng Tết 2027 tại Hà Nội

Website hiển thị đến hạng 20 cho Tết Nguyên đán và Tết Dương lịch, bao gồm các doanh nghiệp đồng hạng. Các mức tiền tính theo triệu đồng/người và dựa trên dự kiến doanh nghiệp kê khai. Trang dẫn đến danh mục báo cáo theo Công văn 8513/SNV-LĐTLDN.

## Xuất bản

1. Đưa các tệp lên nhánh mặc định của repo, bao gồm thư mục ẩn `.github`.
2. Mở **Settings → Pages → Build and deployment** và chọn **GitHub Actions**.
3. Mở **Actions → Cập nhật bảng thưởng Tết Hà Nội → Run workflow** để quét và triển khai lần đầu.
4. Mở URL hiện trong job **deploy** để kiểm tra cả hai bảng và mốc dữ liệu.

Workflow lập lịch hằng ngày lúc 23:59 giờ Hà Nội (16:59 UTC). GitHub Actions chạy theo đơn vị phút và có thể bắt đầu muộn. Repo public có thể bị GitHub tắt lịch sau 60 ngày không có hoạt động. Nếu repo đang phục vụ website khác, tích hợp phần dựng bảng vào workflow Pages hiện có để cùng xuất bản trong một lần triển khai.

## Phạm vi

- Chương trình đọc các bảng Google Sheets và văn bản Google Docs có đường dẫn công khai, theo các biểu mẫu đã đối chiếu trong `data/sources.json`. Nguồn mới được báo trong log để đối chiếu cấu trúc. Biểu mẫu Google Forms là nơi nộp báo cáo.
- Mỗi dịp Tết có bảng xếp hạng riêng theo mức cao nhất. Hạng đồng điểm dùng kiểu 1, 2, 2, 4. Mức thiếu được để trống. Bản ghi trùng nhưng khác số liệu hoặc có đơn vị chưa rõ được loại khỏi bảng.
- Nếu bảng nguồn thay cột hoặc một nguồn trước đây đọc được gặp lỗi, workflow dừng trước bước triển khai để giữ bản Pages đang hiển thị. Đợt 21/11 có một bảng Gia Lâm yêu cầu quyền truy cập. Website hiển thị tình trạng này khi nguồn vẫn chưa mở.
- Thư mục xuất bản chỉ chứa HTML và CSS của hai bảng tổng hợp. Tệp nguồn thô, tên người liên hệ, số điện thoại và địa chỉ chi tiết không được ghi vào bản xuất bản.

## Chạy cục bộ

```sh
python -m pip install -r requirements.txt
python scripts/build.py --snapshot
python -m http.server 8000 --directory _site
```

Mở [localhost:8000](http://localhost:8000) để xem bản dữ liệu ngày 21/11/2026. Chạy `python scripts/build.py` để tải lại nguồn và dựng bản mới.
