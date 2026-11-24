# Bảng xếp hạng thưởng Tết 2027 tại Hà Nội

Website hiển thị toàn bộ doanh nghiệp đủ điều kiện cho Tết Nguyên đán và Tết Dương lịch, mỗi trang 30 doanh nghiệp. Các mức tiền tính theo triệu đồng/người và dựa trên dự kiến doanh nghiệp kê khai. Trang dẫn đến danh mục báo cáo theo Công văn 8513/SNV-LĐTLDN.

Chọn tab theo dịp Tết rồi lọc toàn bộ bảng theo tên doanh nghiệp, phường/xã hoặc mức thưởng cao nhất tối thiểu. Tìm kiếm tên hỗ trợ cả chữ có dấu và không dấu. Kết quả lọc giữ thứ hạng theo toàn bộ dữ liệu của dịp.

## Xuất bản

1. Trong repo `IbrahimVu/BXH`, mở **Settings → Pages → Build and deployment** và chọn **GitHub Actions**.
2. Vào **Actions → Cập nhật bảng thưởng Tết Hà Nội → Run workflow** để chạy thử. Khi mã website hoặc cấu hình thay đổi trên nhánh `master`, workflow xuất bản bản dữ liệu đã đối chiếu đi kèm. Lịch Supabase chạy crawler trước khi xuất bản.
3. Mở URL trong job **deploy** để kiểm tra cả hai bảng và mốc dữ liệu.

## Lịch crawl trên Supabase

Supabase Cron gọi workflow `pages.yml` của GitHub. Mỗi lần chạy thành công, workflow dựng lại hai bảng và xuất bản lên GitHub Pages.

1. Tạo GitHub fine-grained token chỉ cho repo `IbrahimVu/BXH` với quyền **Actions: Read and write**. Lưu token trong **Supabase Vault** với tên `bxh_github_actions_token`.
2. Chạy [supabase/schedule.sql](supabase/schedule.sql) trong SQL Editor của dự án BXH. Tệp cập nhật job `bxh-github-pages-crawl` vào **23:59 giờ Hà Nội** (16:59 UTC) và tạo hoặc cập nhật job `bxh-github-pages-crawl-noon` vào **12:00 giờ Hà Nội** (05:00 UTC).
3. Chạy thử job từ Supabase và kiểm tra phản hồi HTTP cùng lượt chạy mới trong GitHub Actions. Mã HTTP 2xx xác nhận GitHub đã nhận lệnh. Job **deploy** thành công xác nhận site đã cập nhật.
4. Sau khi xác minh Supabase gọi được workflow, đặt repository variable `SUPABASE_MANAGES_CRAWL` thành `true` tại **Settings → Secrets and variables → Actions → Variables** để lịch GitHub cũ bỏ qua bước crawl.

## Phạm vi

- Chương trình kiểm tra danh mục Thư Viện Pháp Luật theo tỉnh, thành và các trang Hà Nội được liên kết. Chương trình đọc Google Sheets và Google Docs công khai theo các biểu mẫu đã đối chiếu trong `data/sources.json`. Nguồn mới được báo trong log để đối chiếu cấu trúc. Biểu mẫu Google Forms là nơi nộp báo cáo.
- Mỗi dịp Tết có bảng xếp hạng riêng theo mức cao nhất. Hạng đồng điểm dùng kiểu 1, 2, 2, 4. Mức thiếu được để trống. Bản ghi trùng nhưng khác số liệu hoặc có đơn vị chưa rõ được loại khỏi bảng.
- Nếu bảng nguồn thay cột hoặc xuất hiện lỗi truy cập mới, workflow dừng trước bước triển khai để giữ bản Pages đang hiển thị. Hai nguồn có vấn đề về quyền truy cập đã xác định là Gia Lâm và Hoàng Mai. Crawler kiểm tra lại cả hai mỗi lượt. Website ghi rõ nguồn nào chưa đọc được trong lần quét.
- Thư mục xuất bản chứa trang tổng hợp, mã bộ lọc và font tiếng Việt. Tệp nguồn thô, tên người liên hệ, số điện thoại và địa chỉ chi tiết không được ghi vào bản xuất bản.

## Chạy cục bộ

```sh
python -m pip install -r requirements.txt
python scripts/build.py --snapshot
python -m http.server 8000 --directory _site
```

Mở [localhost:8000](http://localhost:8000) để xem bản dữ liệu ngày 24/11/2026. Chạy `python scripts/build.py` để tải lại nguồn và dựng bản mới.
