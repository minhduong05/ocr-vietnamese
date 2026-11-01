"""Build a Vietnamese PDF report from the verified handwriting EDA artifacts.

Run from the project root: .venv/Scripts/python.exe scripts/build_eda_pdf_report.py
The original datasets and EDA notebooks are read only.
"""
from pathlib import Path
from collections import Counter
from xml.sax.saxutils import escape
import hashlib
import io
import json
import math
import os
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / 'tmp' / 'pdfs'
ASSETS = TMP / 'assets'
OUTPUT = ROOT / 'output' / 'pdf'
for directory in (TMP, ASSETS, OUTPUT):
    directory.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(TMP / 'matplotlib'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image as PILImage, ImageOps
import pyarrow as pa
import pyarrow.ipc as ipc
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

EDA = ROOT / 'reports' / 'results' / 'eda'
NAMES = ['UIT_HWDB_line', 'viet_htr']
FRAMES = {name: pd.read_csv(EDA/name/'sample_features.csv', keep_default_na=False) for name in NAMES}
SUMMARY = {name: json.loads((EDA/name/'summary.json').read_text(encoding='utf-8')) for name in NAMES}
SHORT = {'UIT_HWDB_line': 'UIT', 'viet_htr': 'VietHTR'}
PALETTE = {'UIT_HWDB_line': '#216A91', 'viet_htr': '#B8682B', 'train': '#216A91', 'test': '#B8682B'}

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.titlesize': 11.5,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.alpha': .17, 'figure.facecolor': 'white', 'savefig.facecolor': 'white'})

def csv(name, filename):
    return pd.read_csv(EDA/name/filename, keep_default_na=False)

def save_chart(fig, name):
    fig.tight_layout(pad=1.2)
    path = ASSETS/f'{name}.png'
    fig.savefig(path, dpi=210, bbox_inches='tight')
    plt.close(fig)
    return path

def ecdf(ax, values, label, color):
    x = np.sort(np.asarray(values))
    ax.plot(x, np.arange(1, len(x)+1)/len(x)*100, label=label, color=color, lw=1.8)

def make_assets():
    figures = {}
    fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.8))
    for ax, name in zip(axs, NAMES):
        count = FRAMES[name].groupby('split').size().reindex(['train', 'test'])
        bars = ax.bar(count.index, count.values, color=[PALETTE[s] for s in count.index])
        ax.bar_label(bars, labels=[f'{n:,}' for n in count], padding=4, fontsize=10)
        ax.set(title=SHORT[name], ylabel='Số mẫu có nhãn'); ax.margins(y=.22)
    figures['splits'] = save_chart(fig, '01_splits')
    for name in NAMES:
        f = FRAMES[name]
        fig, axs = plt.subplots(1, 2, figsize=(7.1, 3.0))
        bins = np.linspace(0, max(170, f.n_chars.max()+1), 36)
        for split in ['train', 'test']:
            g = f[f.split.eq(split)]
            axs[0].hist(g.n_chars, bins=bins, histtype='step', density=True, lw=1.8,
                        label=split, color=PALETTE[split])
            ecdf(axs[1], g.n_chars, split, PALETTE[split])
        axs[0].set(xlabel='Ký tự NFC / dòng', ylabel='Mật độ', title='Phân phối độ dài')
        axs[1].set(xlabel='Ký tự NFC / dòng', ylabel='% dòng tích lũy', title='Đường tích lũy (ECDF)')
        for ax in axs: ax.legend(fontsize=9)
        figures[f'length_{name}'] = save_chart(fig, f'02_lengths_{name}')
    f = FRAMES['UIT_HWDB_line']
    fig, axs = plt.subplots(1, 2, figsize=(7.1, 3.0))
    for split in ['train', 'test']:
        g = f[f.split.eq(split)]
        ecdf(axs[0], g.height, split, PALETTE[split])
        ecdf(axs[1], g.brightness, split, PALETTE[split])
    axs[0].set(xlabel='Chiều cao ảnh gốc (px)', ylabel='% dòng tích lũy', title='Chiều cao ảnh UIT', xlim=(50, 700))
    axs[1].set(xlabel='Độ sáng xám (0-255)', ylabel='% dòng tích lũy', title='Độ sáng thumbnail')
    for ax in axs: ax.legend(fontsize=9)
    figures['uit_shift'] = save_chart(fig, '03_uit_shift')
    f = FRAMES['viet_htr']
    labels = {'flag_low_contrast': 'Tương phản thấp', 'flag_sparse_ink': 'Foreground rất ít',
              'flag_dense_ink': 'Foreground rất nhiều', 'flag_border_ink': 'Nét chạm biên',
              'flag_tiny_height': 'Chiều cao <16 px'}
    fig, ax = plt.subplots(figsize=(7.1, 2.8))
    y = np.arange(len(labels))
    for k, split in enumerate(['train', 'test']):
        g = f[f.split.eq(split)]
        vals = [100*g[col].mean() for col in labels]
        ax.barh(y+(k-.5)*.32, vals, height=.30, color=PALETTE[split], label=split)
    ax.set_yticks(y, labels.values()); ax.invert_yaxis()
    ax.set(xlabel='% ảnh trong split; các nhóm có thể giao nhau', title='Chỉ báo cần xem thủ công - VietHTR')
    ax.legend(fontsize=9)
    figures['quality'] = save_chart(fig, '04_quality')
    fig, axs = plt.subplots(1, 2, figsize=(7.1, 3.0))
    for name in NAMES:
        c = csv(name, 'character_frequencies.csv').sort_values('train', ascending=False)
        values = c.train.to_numpy(float)
        cumulative = np.cumsum(values)/values.sum()*100
        axs[0].plot(np.arange(1,len(values)+1), cumulative, label=SHORT[name], color=PALETTE[name])
        t = csv(name, 'token_frequencies.csv').sort_values('train', ascending=False).train.to_numpy(float)
        axs[1].plot(np.arange(1,len(t)+1), np.cumsum(t)/t.sum()*100, label=SHORT[name], color=PALETTE[name])
    for ax in axs:
        ax.axhline(99, c='#777777', lw=.8, ls='--'); ax.legend(fontsize=9)
        ax.set(ylabel='% lượt xuất hiện tích lũy', ylim=(0,101))
    axs[0].set(title='Ký tự - chỉ dùng train', xlabel='Số loại phổ biến nhất')
    axs[1].set(title='Token chữ - chỉ dùng train', xlabel='Số loại phổ biến nhất (log)', xscale='log')
    figures['coverage'] = save_chart(fig, '05_coverage')
    tones = ['không dấu thanh', 'huyền', 'sắc', 'hỏi', 'ngã', 'nặng']
    fig, ax = plt.subplots(figsize=(7.1, 2.7))
    x = np.arange(len(tones))
    for k,name in enumerate(NAMES):
        t = csv(name, 'tone_frequencies.csv')
        counts = t[t.split.eq('train')].set_index('tone')['count'].reindex(tones, fill_value=0)
        ax.bar(x+(k-.5)*.34, counts/counts.sum()*100, width=.32, color=PALETTE[name], label=SHORT[name])
    ax.set_xticks(x, ['Không thanh', 'Huyền', 'Sắc', 'Hỏi', 'Ngã', 'Nặng'])
    ax.set(ylabel='% trên tất cả chữ cái train', title='Thanh điệu: mẫu số gồm cả phụ âm'); ax.legend(fontsize=9)
    figures['tones'] = save_chart(fig, '06_tones')
    fig, axs = plt.subplots(1, 2, figsize=(7.1, 3.0))
    for name in NAMES:
        f = FRAMES[name]
        ecdf(axs[0], f.n_chars, SHORT[name], PALETTE[name])
        ecdf(axs[1], f.brightness, SHORT[name], PALETTE[name])
    axs[0].set(xlabel='Ký tự NFC / dòng', ylabel='% dòng tích lũy', title='Độ dài hai nguồn')
    axs[1].set(xlabel='Độ sáng (0-255)', ylabel='% ảnh tích lũy', title='Độ sáng hai nguồn')
    for ax in axs: ax.legend(fontsize=9)
    figures['domains'] = save_chart(fig, '07_domains')
    ctc_rows = []
    for name in NAMES:
        f = FRAMES[name]
        for height in [32,48,64]:
            width = np.ceil(f.width*height/f.height)
            for stride in [4,8]:
                fail = width.floordiv(stride).lt(f.ctc_min_steps)
                for split in ['train','test']:
                    select = f.split.eq(split)
                    ctc_rows.append({'dataset':name,'height':height,'stride':stride,'split':split,
                                     'n':int(select.sum()),'n_fail':int(fail[select].sum()),
                                     'fail_percent':float(fail[select].mean()*100)})
    extra_ctc = pd.DataFrame(ctc_rows)
    extra_ctc.to_csv(EDA/'report_ctc_height_scenarios.csv', index=False, encoding='utf-8-sig')
    review_parts = []
    for name in NAMES:
        f = FRAMES[name].copy()
        f['resized_width_H64'] = np.ceil(f.width*64/f.height).astype(int)
        f['approx_steps_S4'] = f.resized_width_H64 // 4
        f['source_dataset'] = name
        review_parts.append(f[f.approx_steps_S4.lt(f.ctc_min_steps)][[
            'source_dataset','sample_id','split','width','height','n_chars','ctc_min_steps',
            'resized_width_H64','approx_steps_S4','text_raw','text_nfc']])
    pd.concat(review_parts, ignore_index=True).to_csv(
        EDA/'report_ctc_review_candidates_H64_S4.csv', index=False, encoding='utf-8-sig')
    fig, ax = plt.subplots(figsize=(7.1,2.7))
    configs = [(32,4),(32,8),(48,4),(64,4)]
    x = np.arange(len(configs))
    for k,name in enumerate(NAMES):
        t = extra_ctc[(extra_ctc.dataset.eq(name)) & extra_ctc.split.eq('train')]
        vals = [t[t.height.eq(h)&t.stride.eq(s)].fail_percent.iloc[0] for h,s in configs]
        bars=ax.bar(x+(k-.5)*.34, vals, width=.32, color=PALETTE[name], label=SHORT[name])
        ax.bar_label(bars, labels=[f'{v:.2f}%' for v in vals], fontsize=8, padding=3)
    ax.set_xticks(x, [f'H={h}, stride={s}' for h,s in configs])
    ax.set(ylabel='% mẫu train không đủ bước', title='CTC: số bước ảnh so với số ký tự cần học', ylim=(0,105))
    ax.legend(fontsize=9)
    figures['ctc'] = save_chart(fig, '08_ctc')
    fig, axs = plt.subplots(1, 2, figsize=(7.1,2.8))
    for ax,name in zip(axs,NAMES):
        t=csv(name,'padding_simulation.csv')
        for strategy,label,color in [('random','Batch ngẫu nhiên','#B8682B'),('bucket_sorted','Sắp rộng lý tưởng','#216A91')]:
            g=t[t.strategy.eq(strategy)]
            ax.plot(g.batch_size,g.padding_waste_percent,'o-',label=label,color=color)
        ax.set(title=SHORT[name],xlabel='Số ảnh / batch',ylabel='% vùng padding',xticks=[8,16,32,64],ylim=(0,58))
        ax.legend(fontsize=8)
    figures['padding'] = save_chart(fig,'09_padding')
    selected = {
        'uit_margin': ('UIT_HWDB_line','train/12/6.jpg'),
        'viet_decoration': ('viet_htr','train/0018408'),
        'viet_two_lines': ('viet_htr','train/0015812'),
        'viet_neighbours': ('viet_htr','train/0035761'),
        'viet_dark': ('viet_htr','train/0024806'),
    }
    opened = {}
    for label,(name,sid) in selected.items():
        row = FRAMES[name].loc[FRAMES[name].sample_id.eq(sid)].iloc[0]
        if name == 'UIT_HWDB_line':
            image = PILImage.open(ROOT/'data'/name/row.image_path)
        else:
            source = ROOT/'data'/name/row.source_shard
            if str(source) not in opened:
                mmap=pa.memory_map(str(source),'r')
                opened[str(source)]=(mmap,ipc.open_stream(mmap).read_all())
            cell=opened[str(source)][1]['image'][int(row.source_row)].as_py()
            image=PILImage.open(io.BytesIO(cell['bytes']))
        image=ImageOps.exif_transpose(image).convert('RGB')
        path=ASSETS/f'{label}.png';image.save(path);figures[label]=path
    return figures, extra_ctc

FIGS, CTC = make_assets()
font_root = Path('C:/Windows/Fonts')
for name, file in [('Body','arial.ttf'),('Body-Bold','arialbd.ttf'),('Body-Italic','ariali.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(font_root/file)))
pdfmetrics.registerFontFamily('Body', normal='Body',bold='Body-Bold',italic='Body-Italic',boldItalic='Body-Bold')
NAVY=colors.HexColor('#14334C');TEAL=colors.HexColor('#216A91');INK=colors.HexColor('#253443')
MUTED=colors.HexColor('#5B6C79'); LIGHT=colors.HexColor('#EAF3F7')
PAGE_W,PAGE_H=A4
WIDTH=PAGE_W-96
STYLES={
    'body':ParagraphStyle('body',fontName='Body',fontSize=10.1,leading=14.3,textColor=INK,spaceAfter=8),
    'small':ParagraphStyle('small',fontName='Body',fontSize=8.5,leading=11.5,textColor=MUTED,spaceAfter=6),
    'title':ParagraphStyle('title',fontName='Body-Bold',fontSize=20,leading=25,textColor=NAVY,spaceAfter=13),
    'sub':ParagraphStyle('sub',fontName='Body-Bold',fontSize=11.4,leading=15,textColor=TEAL,spaceBefore=8,spaceAfter=6),
    'cell':ParagraphStyle('cell',fontName='Body',fontSize=9,leading=12,textColor=INK),
    'head':ParagraphStyle('head',fontName='Body-Bold',fontSize=9,leading=12,textColor=colors.white),
    'cover':ParagraphStyle('cover',fontName='Body-Bold',fontSize=31,leading=38,textColor=NAVY,spaceAfter=18),
    'kicker':ParagraphStyle('kicker',fontName='Body-Bold',fontSize=9,leading=12,textColor=TEAL,spaceAfter=8),
}

def clean(text):
    return unicodedata.normalize('NFC', str(text)).replace('—','-').replace('–','-').replace('\u2011','-')
def P(text,style='body'):
    return Paragraph(clean(text),STYLES[style])
def para(text):
    return P(text)
def sub(text):
    return P(text,'sub')
def small(text):
    return P(text,'small')
def gap(h=6):
    return Spacer(1,h)
def tbl(headers,rows,widths=None):
    if widths is None: widths=[WIDTH/len(headers)]*len(headers)
    else: widths=[WIDTH*w/sum(widths) for w in widths]
    data=[[P(escape(str(c)),'head') for c in headers]]+[[P(escape(str(c)),'cell') for c in row] for row in rows]
    table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F1F5F7'),colors.white]),
        ('LINEBELOW',(0,0),(-1,0),.6,NAVY),('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#D9E3E8'))]))
    table.spaceAfter=10
    return table
def box(text):
    table=Table([[P(text)]],colWidths=[WIDTH],hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('LINEBEFORE',(0,0),(0,-1),4,TEAL),
        ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    table.spaceAfter=10
    return table
def figure(key,caption,maxh=230):
    path=FIGS[key]
    with PILImage.open(path) as image: w,h=image.size
    factor=min(WIDTH/w,maxh/h)
    image=Image(str(path),width=w*factor,height=h*factor,hAlign='CENTER')
    return [image,gap(4),small(caption)]

PAGES=[]
def page(title,*items,kicker=None):
    number=len(PAGES)+1
    title_para=P(title,'title');title_para._bookmarkName=f'page_{number}'
    flows=[P(kicker or f'PHẦN {number:02d} / 27','kicker'),title_para,*items]
    PAGES.append((title,flows))

page('Từ hiểu dữ liệu đến huấn luyện mô hình',
    P('CHỮ VIẾT TAY<br/>TIẾNG VIỆT','cover'),
    para('Báo cáo nhận xét chi tiết cho <b>UIT_HWDB_line</b> và <b>viet_htr</b>. '
         'Tài liệu dành cho người đang làm thống kê, phân tích khám phá và chuẩn bị dữ liệu huấn luyện; '
         'thuật ngữ tiếng Anh được giải thích ngay khi sử dụng và có bảng tra ở cuối.'),
    tbl(['Kết quả đã kiểm tra','UIT_HWDB_line','viet_htr'],[
        ['Mẫu có nhãn / ảnh giải mã được','7.229 / 7.229','60.247 / 60.247'],
        ['Train / test hiện có','7.028 / 201','59.247 / 1.000'],
        ['Ký tự NFC khác nhau','161','404'],
        ['Ảnh cùng pixel nằm ở cả train và test','0 nhóm','0 nhóm'],
    ],[2.2,1.25,1.25]),
    box('<b>Đề xuất khởi đầu:</b> giữ nguyên test; lập tập kiểm định từ train; chuẩn hóa nhãn có truy vết; '
        'dùng ảnh cao 64 px, giữ tỷ lệ và giảm chiều ngang khoảng 4 lần cho mốc CTC đầu tiên. '
        'Rà soát riêng các ảnh có lề lớn, nhiều dòng hoặc nét trang trí trước khi chốt cấu hình.'),
    para('<b>Ba việc ưu tiên:</b> xử lý 44 ảnh UIT chưa có nhãn; kiểm tra 15 nhãn VietHTR có ký tự điều khiển; '
         'giải quyết 11 mẫu train chưa đủ bước CTC ngay cả trong mô phỏng cao 64 px, stride 4.'),
    small('Ngày báo cáo: 01/11/2026 (Asia/Bangkok). Số liệu nền: các notebook và bảng EDA đã chạy trên toàn bộ '
          '67.476 cặp ảnh-nhãn. Đây là đánh giá dữ liệu và đề xuất thí nghiệm, chưa phải kết quả huấn luyện.'),
    kicker='BÁO CÁO PHÂN TÍCH VÀ PHƯƠNG ÁN CHUẨN BỊ DỮ LIỆU')

page('Cách đọc báo cáo và hiểu các con số',
    para('<b>EDA - Exploratory Data Analysis</b> là phân tích khám phá dữ liệu: xem dữ liệu có gì, phân bố ra sao '
         'và có điểm nào cần kiểm tra trước khi huấn luyện. Một <b>sample</b> là một mẫu, ở đây là một ảnh cùng '
         'đoạn chữ mô tả ảnh đó. <b>Label / annotation</b> là nhãn, tức đoạn chữ chuẩn cần nhận dạng.'),
    tbl(['Từ gặp trong báo cáo','Hiểu đơn giản'],[
        ['Train / validation / test','Tập học / tập chọn cấu hình và thời điểm dừng / tập đánh giá cuối cùng. Test không dùng để chọn mô hình.'],
        ['Median - trung vị','Giá trị ở giữa khi sắp xếp. Trung vị 71 ký tự nghĩa là khoảng một nửa dòng không dài hơn 71 ký tự.'],
        ['P95 / P99 - phân vị','P95 là mức mà khoảng 95% mẫu không vượt quá; phần còn lại vẫn cần được xử lý.'],
        ['Pixel (px) / aspect ratio','Điểm ảnh / tỷ lệ chiều rộng chia chiều cao. Tỷ lệ lớn thường là ảnh dài và thấp.'],
        ['Token trong EDA này','Đơn vị tách bằng khoảng trắng hoặc chuỗi chữ Unicode. Với tiếng Việt thường gần với âm tiết, chưa phải từ đã tách nghĩa.'],
    ],[1.5,3.5]),
    sub('Đi theo lộ trình nào?'),
    para('Trang 3-11: nhận xét thống kê từng bộ và so sánh. Trang 12-13: ví dụ ảnh đã xem trực tiếp. '
         'Trang 14-20: quy trình làm sạch, chia tập và đưa ảnh vào mô hình. Trang 21-24: huấn luyện, đánh giá '
         'và điều kiện nghiệm thu. Trang 25-27: từ điển thuật ngữ và nguồn đối chiếu.'),
    box('<b>Ba mức bằng chứng:</b> số đếm và phân vị được tính từ toàn bộ dữ liệu; chỉ báo ảnh chỉ gợi ý kiểm tra; '
        'cấu hình huấn luyện là phương án cần thử trên validation. Không biến một gợi ý thành kết luận chắc chắn.'),
    small('Thống kê ký tự sử dụng code point Unicode sau NFC, gồm khoảng trắng. Đây không phải số nét bút, '
          'không phải số chữ cái ngữ nghĩa và cũng không luôn trùng số ký tự nhìn thấy. Nguồn: [D1], [D2].'))

page('Quy mô và độ đầy đủ của dữ liệu',
    *figure('splits','Hình 1. Số cặp ảnh-nhãn theo split gốc; hai biểu đồ có trục tung riêng.',190),
    para('<b>UIT:</b> có 7.273 tệp ảnh JPG được kiểm kê nhưng chỉ 7.229 cặp ảnh-nhãn. '
         '44 ảnh ở thư mục train_data/10 chưa có nhãn tương ứng trong label.json; các ảnh này được ghi nhận '
         'nhưng chưa nằm trong thống kê ảnh có nhãn. Có 249 nhóm thư mục train và 6 nhóm test.'),
    para('<b>VietHTR:</b> có 60.247 cặp lưu trong Arrow, một định dạng lưu bảng dữ liệu; '
         'ảnh được nhúng dạng bytes, tức dữ liệu nhị phân. Thư mục save_to_disk có ba shard train '
         '(ba phần tệp) và một shard test. Cấu trúc cục bộ chỉ cung cấp image và text, không có ID người viết.'),
    tbl(['Kiểm tra','Kết quả','Ý nghĩa thực hành'],[
        ['Giải mã ảnh có nhãn','67.476 / 67.476 thành công','Không gặp tệp không mở được; chưa chứng minh nhãn đúng.'],
        ['Nhãn rỗng / sai kiểu','0 / 0 ở cả hai bộ','Đầu vào có đủ chuỗi nhãn cho các mẫu đã lập chỉ mục.'],
        ['Tỷ lệ test UIT / VietHTR','2,78% / 1,66%','Giữ split để so sánh; cần tạo validation từ phần train.'],
    ],[1.6,1.2,2.5]),
    box('<b>Xử lý 44 ảnh:</b> tìm lại nhãn gốc hoặc ghi nhãn có kiểm duyệt. Nếu chưa khôi phục được, để trạng thái '
        'pending_annotation - chờ nhãn - và chưa dùng cho huấn luyện có giám sát. Không gán nhãn rỗng hoặc đoán nhãn từ tên tệp.'),
    small('Nguồn: [D1], [D2] source_inventory.csv, source_issues.csv, image_coverage.csv. '
          'Mã thư mục chưa được xác nhận là mã người viết; không báo cáo 255 người viết từ 255 thư mục.'))

page('UIT: nhãn dài và độ biến thiên nội dung',
    *figure('length_UIT_HWDB_line','Hình 2. Độ dài UIT: histogram là mật độ, không phải số mẫu; ECDF là tỷ lệ tích lũy.',215),
    tbl(['Độ dài NFC','Train','Test'],[
        ['Trung vị / trung bình','71 / 67,81','68 / 65,18'],
        ['Ngắn nhất / dài nhất','2 / 158 ký tự','3 / 99 ký tự'],
        ['Token cách trắng trung vị','16','15'],
        ['Toàn bộ dữ liệu: P95','90 ký tự','Tính chung hai split'],
    ],[2.5,1.5,1.5]),
    para('Đường tích lũy giúp đọc câu hỏi thực tế: với giới hạn đầu ra dài bao nhiêu thì giữ được phần lớn dòng? '
         'Những dòng rất ngắn có thể chỉ là cuối đoạn văn, vì vậy không nên xóa chỉ vì nằm xa trung vị. '
         'Một dòng dài 158 ký tự cần nhiều vị trí đầu ra hơn dòng dài 20 ký tự.'),
    para('Không phát hiện nhãn UIT rỗng, thay đổi sau NFC, khoảng trắng lặp hoặc ký tự điều khiển trong các kiểm tra đã chạy. '
         'Đây là tín hiệu thuận lợi về định dạng, nhưng chưa phải chứng nhận rằng từng dấu hoặc từng từ đều khớp ảnh.'),
    box('<b>Hệ quả khi train:</b> giữ nhãn dòng đầy đủ; thống nhất ký tự khoảng trắng và dấu câu; '
        'kiểm tra độ dài đầu ra của mạng với mọi dòng train. Không cắt nhãn theo độ dài cố định để ép khớp mô hình.'),
    small('Nguồn: [D1] text_descriptive_statistics.csv, label_quality_flags.csv, sample_features.csv. '
          'Histogram so sánh hình dạng vì train nhiều mẫu hơn test; cột cao hơn không trực tiếp có nghĩa nhiều ảnh hơn.'))

page('UIT: hình học ảnh và khác biệt train/test',
    *figure('uit_shift','Hình 3. ECDF chiều cao chỉ hiển thị vùng 50-700 px để thấy phần lớn mẫu; thống kê vẫn tính toàn bộ.',210),
    para('Tất cả ảnh UIT có chiều rộng 2.048 px. Chiều cao biến thiên mạnh: train từ 72 đến 2.022 px, '
         'test từ 129 đến 2.290 px. Vì vậy, ảnh cùng chiều rộng không đồng nghĩa dòng chữ có cùng cỡ hoặc cùng lượng nền.'),
    tbl(['Chỉ số trung vị','Train','Test','Nhận xét'],[
        ['Chiều cao gốc','151 px','181 px','Test cao hơn 30 px.'],
        ['Độ sáng mức xám','220,84','226,73','Test sáng hơn.'],
        ['Tương phản (độ lệch chuẩn xám)','38,98','34,37','Test có tương phản thấp hơn.'],
        ['Tỷ lệ foreground Otsu','9,25%','7,37%','Tỷ lệ vùng tối ước lượng khác nhau.'],
    ],[2.1,1,1,1.8]),
    para('<b>Distribution shift - dịch chuyển phân phối</b> là sự khác nhau giữa dữ liệu học và dữ liệu đánh giá. '
         'Khoảng cách KS của độ sáng là 0,477; của chiều cao là 0,450. Đây là chênh lệch lớn nhất giữa hai đường tích lũy, '
         'không phải tỷ lệ ảnh sai hay tỷ lệ lỗi nhận dạng.'),
    box('<b>Đề xuất:</b> tránh chuẩn hóa bằng một giá trị suy ra từ test. Dùng tăng cường sáng/tương phản nhẹ trên train '
        'và kiểm tra validation. Rà soát ảnh quá cao hoặc nhiều lề trước khi resize; ảnh thừa nền làm chữ nhỏ đi đáng kể.'),
    small('Nguồn: [D1] distribution_shift.csv và sample_features.csv. Chất lượng xám được tính trên thumbnail giữ tỷ lệ, '
          'không phải phép đo màu đã hiệu chuẩn. Chưa có bằng chứng để quy khác biệt cho máy quét hay người viết.'))

page('VietHTR: định dạng nhãn và các dòng dài',
    *figure('length_viet_htr','Hình 4. VietHTR có test dài hơn train rõ hơn UIT; ECDF test dịch sang phải.',210),
    tbl(['Chỉ số','Train','Test'],[
        ['Trung vị ký tự NFC','44','52,5'],
        ['Độ dài trung bình','45,38','53,64'],
        ['Khoảng độ dài','4-157','11-166'],
        ['Khoảng trắng lặp','130 dòng','2 dòng'],
        ['Ký tự điều khiển','15 dòng','0'],
        ['Nhãn thay đổi biểu diễn sau NFC','1 dòng','0'],
    ],[2.7,1.3,1.3]),
    para('Trong 15 dòng có ký tự điều khiển: 14 nhãn có tab (U+0009), một nhãn có xuống dòng (U+000A). '
         'Tab là ký tự căn cột; xuống dòng là ký tự chuyển hàng. Hai loại này không được xử lý giống nhau '
         'mà chưa nhìn ảnh. Ví dụ train/0015812 thực sự chứa hai dòng, đã minh họa ở trang 13.'),
    para('Test dài hơn còn thể hiện ở token cách trắng: trung vị 13 so với 11 ở train, KS D = 0,295. '
         'Những dòng dài có thể gây lỗi thiếu bước CTC hoặc bị mất phần cuối nếu đặt giới hạn chiều rộng quá thấp.'),
    box('<b>Đề xuất:</b> chuẩn hóa NFC; xem 15 nhãn điều khiển cùng ảnh; quy định khoảng trắng trong văn bản một dòng. '
        'Không gộp hai dòng thành một nhãn một dòng chỉ bằng thao tác thay ký tự xuống dòng thành dấu cách.'),
    small('Nguồn: [D2] label_quality_flags.csv, flagged_labels.csv, distribution_shift.csv. Các cờ có thể giao nhau, '
          'vì vậy không cộng số dòng ở các hàng để suy ra số mẫu lỗi duy nhất.'))

page('VietHTR: chỉ báo ảnh không phải phán quyết',
    *figure('quality','Hình 5. Tỷ lệ có cờ kiểm tra; các nhóm chồng lấp. Ngưỡng được dùng để tìm ứng viên.',205),
    tbl(['Tín hiệu trên toàn bộ 60.247 ảnh','Số ảnh','Cách hiểu'],[
        ['Tương phản xám <10','130','Có thể tối/mờ; cần xem chữ còn đọc được không.'],
        ['Foreground Otsu >70%','1.278','Có thể nền tối, tô nền hoặc phân ngưỡng sai.'],
        ['Tỷ lệ mực ở biên >20%','16.266','Nét, dòng kẻ hoặc chữ hàng bên cạnh có thể chạm biên.'],
        ['Chiều cao ảnh <16 px','69','Nguy cơ thiếu chi tiết dấu; phóng to không tạo lại chi tiết đã mất.'],
        ['Ít nhất một cờ chất lượng','16.416','Đây là hợp của các nhóm, không phải tổng số cờ.'],
    ],[2.5,.8,2.6]),
    para('<b>Foreground</b> là phần thuật toán ước lượng là mực/chữ; <b>background</b> là nền. '
         '<b>Otsu</b> chọn một ngưỡng độ sáng để tách hai phần. Ảnh chụp giấy có bóng, dòng kẻ hoặc nền không đều '
         'có thể làm ngưỡng này phân loại sai gần cả ảnh thành mực.'),
    box('<b>Không xóa tự động 16.416 mẫu.</b> Đầu tiên rà soát theo nhóm nguy cơ và mẫu đại diện; '
        'ưu tiên ảnh nhiều dòng, cắt mất chữ, nhãn không khớp. Một ảnh tối nhưng còn đọc được có thể vẫn hữu ích '
        'để mô hình học điều kiện chụp thực tế.'),
    small('Nguồn: [D2] image_flag_percentages.csv, sample_features.csv; ngưỡng chi tiết ở notebook. '
          'Không có số đo độ chính xác OCR nào được suy ra từ các cờ này.'))

page('Bảng chữ cái, ký tự hiếm và đuôi dài',
    *figure('coverage','Hình 6. Độ bao phủ tính trên lượt xuất hiện trong train; ký tự bao gồm khoảng trắng.',215),
    tbl(['Đặc trưng','UIT','VietHTR'],[
        ['Loại ký tự NFC toàn bộ / train','161 / 161','404 / 404'],
        ['Ký tự xuất hiện không quá 10 lần','9 loại','164 loại'],
        ['Số loại phủ 99% lượt ký tự train','105','118'],
        ['Loại token chữ trong train','2.648','10.773'],
    ],[2.8,1.2,1.2]),
    para('<b>Long tail - đuôi dài</b> nghĩa là một số ít loại xuất hiện rất nhiều, còn rất nhiều loại xuất hiện ít. '
         'VietHTR có 404 loại ký tự nhưng 118 loại đã phủ 99% lượt. Phần 1% còn lại vẫn chứa chữ và ký hiệu hợp lệ, '
         'không được xem là vô ích chỉ vì hiếm.'),
    para('VietHTR chứa cả ký hiệu toán học, chữ cái Hy Lạp, chỉ số trên/dưới và các ký tự ngoài bảng chữ cái '
         'tiếng Việt thông thường. Một số là nội dung học tập hợp lệ; một số cần đối chiếu nhãn. '
         'Không dùng bộ lọc chỉ giữ a-z hoặc tự bỏ mọi ký hiệu lạ.'),
    box('<b>Vocab - bảng mã đầu ra:</b> xây từ nhãn train đã chuẩn hóa sau khi tách validation, lưu ánh xạ ký tự sang số. '
        '161 ký tự UIT đều có trong 404 ký tự train VietHTR hiện tại; điều này không bảo đảm giữ nguyên sau làm sạch và chia lại.'),
    small('Nguồn: [D1], [D2] character_frequencies.csv, rare_characters.csv, train_vocabulary_coverage.csv. '
          'Độ bao phủ 99% lượt không có nghĩa 99% dòng không chứa ký tự hiếm.'))

page('Tiếng Việt: giữ cả dấu thanh và dấu phụ',
    *figure('tones','Hình 7. Phân bố dấu thanh trong ký tự chữ cái train. Không thanh gồm cả phụ âm, không chỉ thanh ngang.',195),
    tbl(['Thành phần','Ví dụ','Tại sao quan trọng'],[
        ['Dấu thanh','a, à, á, ả, ã, ạ','Thay dấu có thể đổi nghĩa; cần giữ trong nhãn và ảnh.'],
        ['Dấu phụ tạo chữ cái','a / ă / â; o / ô / ơ; u / ư','Đây là những chữ cái khác nhau trong bảng mã đầu ra.'],
        ['Kết hợp hai loại dấu','ắ = nguyên âm ă + thanh sắc','Nét nhỏ phía trên vẫn là thông tin cần nhận dạng.'],
        ['Chữ hoa / chữ thường','Đ / đ; A / a','Không tự đổi hết sang chữ thường nếu mục tiêu là chép đúng ảnh.'],
    ],[1.3,1.6,2.5]),
    para('<b>Unicode NFC</b> đưa các cách mã hóa tương đương về dạng chuẩn ghép khi có thể. '
         'Ví dụ một chữ có dấu có thể lưu bằng một code point ghép sẵn hoặc nhiều code point kết hợp; '
         'NFC giúp so sánh và mã hóa nhất quán. NFC giữ dấu tiếng Việt. [T1]'),
    para('NFKC là chuẩn hóa tương thích, có thể làm thay đổi cách thể hiện một số ký hiệu. '
         'Với dữ liệu có số khoanh tròn, chỉ số và toán học, báo cáo chọn NFC làm mặc định; '
         'chỉ áp dụng quy tắc gộp ký hiệu khi đã xác định rõ mục tiêu và có nhật ký thay đổi.'),
    box('<b>Đối với ảnh:</b> khi cắt lề hoặc xoay, phải giữ khoảng đệm trên/dưới để không mất dấu. '
        'Không lật ngang; không dùng làm mờ hay ăn mòn nét mạnh vì có thể xóa dấu hỏi, ngã, chấm nặng.'),
    small('Nguồn thống kê: [D1], [D2] tone_frequencies.csv, vowel_base_tone_distribution.csv. '
          'Nguồn quy tắc chuẩn hóa: [T1]. Đây là lý do phải tách dấu thanh và dấu phụ khi phân tích.'))

page('Trùng nhãn, trùng ảnh và nguy cơ rò rỉ',
    tbl(['Chỉ số toàn bộ dữ liệu','UIT','VietHTR'],[
        ['Nhóm có nhãn chuẩn so sánh lặp','505','4.022'],
        ['Số mẫu thuộc các nhóm nhãn lặp','1.360','11.597'],
        ['Nội dung nhãn riêng biệt giao train/test','61','171'],
        ['Dòng test có nội dung đã có ở train','62 / 201 (30,85%)','174 / 1.000 (17,40%)'],
        ['Nhóm ảnh trùng byte / pixel','0 / 0','0 / 0'],
        ['Nhóm dHash giống nhau','4','224'],
    ],[2.7,1.3,1.6]),
    para('<b>Data leakage - rò rỉ dữ liệu</b> xảy ra khi thông tin không hợp lệ từ phần đánh giá lọt vào quá trình học '
         'hoặc chọn mô hình, làm kết quả trông tốt hơn thực tế. Một ảnh trùng hệt nằm ở train và test là nguy cơ rõ. '
         'Hai người viết cùng câu chưa đủ kết luận là cùng ảnh hay cùng người viết.'),
    para('<b>SHA-256</b> là mã băm, giống dấu vân tay số dùng để so khớp chính xác. Hash byte so tệp mã hóa; '
         'hash pixel so ảnh RGB và kích thước sau chuẩn hóa hướng hiển thị. <b>dHash</b> rút gọn hình thái thành 64 bit '
         'để tìm ứng viên giống nhau. Hai ảnh cùng dHash có thể khác nhau, nhất là các dòng chữ dài.'),
    para('VietHTR có 9 nhóm dHash xuất hiện ở nhiều split và 145 nhóm dHash chứa nhiều nhãn. '
         '<b>Không diễn giải các con số này là 145 nhóm gán nhãn sai</b>: chỉ hash pixel trùng với nhãn khác '
         'mới là bằng chứng xung đột ảnh chính xác trong phép kiểm tra này, và số nhóm như vậy hiện bằng 0.'),
    box('<b>Hành động:</b> giữ test gốc; rà soát ứng viên dHash bằng ảnh; báo thêm CER cho nội dung test đã gặp/chưa gặp. '
        'Nếu làm bộ chia nghiêm ngặt theo nội dung, tạo phiên bản thí nghiệm riêng, không âm thầm đổi '
        'benchmark - bộ đánh giá dùng làm mốc.'),
    small('Nguồn: [D1], [D2] duplicate_summary.csv, duplicate_dhash.csv và sample_features.csv. '
          'Nhãn so sánh đã qua NFC và gộp khoảng trắng, giữ hoa/thường và dấu. Không kiểm tra toàn bộ bản sao gần giống.'))

page('Hai nguồn khác nhau: nên gộp như thế nào?',
    *figure('domains','Hình 8. Phân phối toàn bộ hai nguồn. Biểu đồ độ sáng phản ánh thumbnail, không phải thang đo chất lượng.',210),
    para('UIT có dòng dài hơn về nhãn (trung vị chung 71 so với 45 ký tự) và ảnh lớn hơn '
         '(hai trung vị riêng: 2.048 x 152 px so với 635 x 59 px). VietHTR đa dạng hơn về ký tự và điều kiện ảnh. '
         'Những khác biệt này là khác biệt miền dữ liệu, tức <b>domain</b>, chứ chưa chứng minh bộ nào khó hơn.'),
    para('Gộp nguyên train sẽ có 66.275 mẫu trước làm sạch: UIT chiếm 10,60%, VietHTR 89,40%. '
         'Nếu lấy mẫu hoàn toàn theo số lượng, mô hình sẽ gặp VietHTR nhiều hơn khoảng 8,43 lần. '
         'Cần đánh giá riêng từng bộ để tránh điểm tổng che đi việc một nguồn bị học kém.'),
    tbl(['Phương án','Mục đích','Điều kiện so sánh'],[
        ['Train riêng từng nguồn','Tạo mốc tham chiếu hiểu nguồn nào cần xử lý gì','Giữ cùng quy tắc nhãn và chỉ số.'],
        ['Gộp theo tỷ lệ tự nhiên','Mốc đơn giản cho dữ liệu kết hợp','Báo riêng CER/WER mỗi bộ.'],
        ['Gộp, lấy mẫu khoảng 25% UIT / 75% VietHTR','Thử giảm ưu thế số lượng của VietHTR','Là giả thuyết; chọn bằng validation, theo dõi quá khớp UIT.'],
    ],[1.5,2,2]),
    box('Không thấy nhãn chuẩn so sánh hoặc hash pixel giao giữa hai nguồn trong bốn cặp split đã kiểm tra. '
        'Kết quả này không chứng minh hai nguồn độc lập theo người viết và không loại trừ ảnh đã nén lại/cắt khác.'),
    small('Nguồn: [D1], [D2] two_datasets_summary.csv, cross_dataset_overlap.csv, sample_features.csv. '
          'Tỷ lệ lấy mẫu 25/75 là đề xuất thí nghiệm của báo cáo, không phải thông số tối ưu đã đo.'))

page('Ví dụ ảnh 1: lề trắng và chữ trang trí',
    *figure('uit_margin','Ví dụ A - UIT train/12/6.jpg, 2.048 x 741 px. Giữ nguyên ảnh gốc trong minh họa.',155),
    para('<b>Quan sát trực tiếp:</b> dòng chữ ở sát phần dưới trong khi vùng phía trên phần lớn là nền. '
         'Khi ép cả chiều cao 741 px về 64 px, chiều cao nét chữ thực tế còn ít hơn mức kỳ vọng. '
         'Mẫu này vẫn thiếu bước trong mô phỏng CTC cao 64, stride 4.'),
    para('<b>Cách xử lý:</b> cắt lại vùng dòng có biên an toàn, giữ đủ dấu và nét lên/xuống; ghi tọa độ cắt, '
         'lưu ảnh dẫn xuất riêng và kiểm tra lại nhãn. Không tự bỏ mọi thành phần nhỏ phía trên vì có thể là dấu tiếng Việt.'),
    *figure('viet_decoration','Ví dụ B - VietHTR train/0018408, 294 x 180 px. Ảnh có dòng chữ nhỏ phía trên và hình/nét trang trí lớn phía dưới.',165),
    para('<b>Quan sát trực tiếp:</b> phần trang trí chiếm tỷ trọng lớn và khác với chuỗi chữ được gán nhãn. '
         'Cắt hộp bao toàn bộ foreground sẽ vẫn giữ cả trang trí, nên chưa giải quyết đúng vấn đề.'),
    box('<b>Quyết định đề xuất:</b> đưa các mẫu này vào hàng đợi review - kiểm tra thủ công. '
        'Cắt vùng đúng dòng nếu xác nhận được đầy đủ chữ; nếu chưa chắc, tạm cách ly khỏi train chính và lưu lý do.'),
    small('Nguồn ảnh gốc: [D3]. Đây là nhận xét trên các mẫu cụ thể, không suy rộng rằng mọi ảnh cao hoặc mọi ảnh thư pháp đều lỗi.'))

page('Ví dụ ảnh 2: hai dòng, hàng lân cận và nền tối',
    *figure('viet_two_lines','VietHTR train/0015812. Nhãn gốc có xuống dòng: “9 bộ quần áo may hết số mét vải là:” rồi “21:9=2(m)”.',85),
    para('<b>Hai dòng thật:</b> ảnh thể hiện hai hàng chữ. Với mô hình nhận dạng một dòng, nên tách ảnh và nhãn '
         'thành hai cặp sau kiểm duyệt, hoặc để nhóm riêng cho mô hình nhiều dòng. Chỉ thay xuống dòng bằng dấu cách '
         'không tạo được thứ tự đọc một dòng trong ảnh.'),
    *figure('viet_neighbours','VietHTR train/0035761. Dòng được gán nhãn nằm giữa, còn nét chữ hàng trên/dưới lọt vào khung.',115),
    para('<b>Chữ hàng bên cạnh:</b> mô hình có thể nhìn thấy nét không có trong nhãn. '
         'Cần cắt lại đúng hàng giữa với biên đủ giữ dấu; nếu không tách được, tạm cách ly hoặc sửa bài toán nhận dạng.'),
    *figure('viet_dark','VietHTR train/0024806. Ảnh tối, foreground Otsu khoảng 99,29%.',65),
    para('<b>Ảnh tối:</b> kết quả Otsu gần 100% không có nghĩa gần toàn ảnh là chữ. '
         'Ảnh gốc vẫn có chữ nhìn thấy nhưng khó đọc; cần xem bản gốc và cân nhắc điều chỉnh sáng/tương phản '
         'có kiểm soát, không tự tạo thêm nét hoặc khẳng định nhãn đúng.'),
    box('Bốn quyết định khác nhau có thể cần đến: giữ nguyên, cải thiện ánh sáng, cắt lại, hoặc tạm cách ly. '
        'Ngưỡng thống kê chỉ giúp tìm mẫu; quyết định phải dựa cả ảnh, nhãn và mục tiêu mô hình.'),
    small('Nguồn: [D3]; mã mẫu truy vết về đúng shard/row trong sample_features.csv. Chưa sửa ảnh hoặc nhãn nguồn.'))

page('Chính sách làm sạch nhãn có thể kiểm tra lại',
    tbl(['Tình huống','Quy tắc đề xuất','Giữ lại bằng chứng'],[
        ['NFC khác nhãn gốc','Đưa text_clean về NFC; giữ dấu và hoa/thường','text_raw, text_clean, normalization_version.'],
        ['Tab trong nhãn một dòng','Xem ảnh; nếu chỉ là căn lề, đổi thành một dấu cách','sample_id, vị trí ký tự và quy tắc đã áp dụng.'],
        ['Nhiều dấu cách','Sau kiểm tra chính sách, gộp thành một dấu cách trong bản chuẩn dùng chung','Văn bản trước/sau; áp dụng cùng quy ước khi chấm điểm.'],
        ['Xuống dòng trong ảnh nhiều dòng','Tách đúng từng dòng hoặc cách ly khỏi tập một dòng','Quan hệ mẫu cha-con, tọa độ cắt và nhãn của từng ảnh con.'],
        ['Ký tự toán học / ít gặp','Giữ nếu ảnh thể hiện ký tự đó; xem lại nếu nghi gán sai','Ảnh kiểm tra và quyết định người duyệt.'],
        ['Lỗi chính tả trong chữ viết','Chép đúng nội dung ảnh nếu mục tiêu là phiên âm nguyên văn','Không tự sửa bằng từ điển hoặc mô hình ngôn ngữ.'],
    ],[1.35,2.25,1.85]),
    para('Tạo ba trường tách biệt: <b>text_raw</b> là nhãn gốc; <b>text_clean</b> là nhãn phục vụ học/chấm điểm '
         'theo chính sách công bố; <b>text_compare</b> chỉ phục vụ tìm nhãn lặp. Tránh dùng tên “clean” cho chuỗi '
         'đã bỏ dấu hoặc bỏ ký tự mà không mô tả chính xác thao tác.'),
    box('<b>Test:</b> bảo toàn ảnh/nhãn gốc để đối chiếu. Nếu báo điểm sau chuẩn hóa, cùng một quy tắc xác định trước '
        'phải áp dụng cho cả dự đoán và nhãn chuẩn; ghi rõ đây là quy ước chấm. Không sửa riêng nhãn test để làm điểm tốt hơn.'),
    sub('Đầu ra sau bước này'),
    para('Một tệp quy tắc chuẩn hóa có phiên bản, bảng thay đổi từng mẫu, danh sách mẫu đang chờ duyệt '
         'và manifest đã cập nhật. Các thao tác tự động phải chạy lặp lại cho cùng kết quả, tức có tính <b>deterministic</b>.'),
    small('Căn cứ dữ liệu: [D1], [D2] flagged_labels.csv. Căn cứ NFC: [T1]. Quy tắc tab, khoảng trắng và xử lý '
          'ảnh nhiều dòng là chính sách được đề xuất cho bài toán một dòng, cần phê duyệt trong nhóm nghiên cứu.'))

page('Đưa hai định dạng về một manifest chung',
    para('<b>Manifest</b> là tệp danh mục: mỗi dòng mô tả một mẫu, ảnh nằm ở đâu, nhãn gì, thuộc tập nào '
         'và đã qua bước xử lý nào. Có thể dùng JSONL - mỗi dòng là một đối tượng JSON - để chứa metadata dễ mở rộng. '
         'Không cần chép toàn bộ dữ liệu ảnh vào RAM.'),
    tbl(['Nhóm trường','Trường nên lưu','Lợi ích'],[
        ['Định danh','sample_id, source_dataset, source_split','Không lẫn hai nguồn hoặc train/test gốc.'],
        ['Vị trí ảnh','image_path; hoặc source_shard + source_row','Hỗ trợ JPG và ảnh nhúng Arrow.'],
        ['Văn bản','text_raw, text_clean, normalization_version','Truy vết thay đổi và tái lập cách chấm.'],
        ['Hình học và băm','width, height, sha256_pixels','Kiểm tra ảnh trùng, resize và lập bucket.'],
        ['Nhóm và kiểm duyệt','group_id, review_status, exclusion_reason','Chia nhóm phù hợp, biết mẫu nào chưa sẵn sàng.'],
        ['Phiên bản chia tập','train/val/test, split_version, seed','Tái lập thí nghiệm và kiểm tra giao tập.'],
    ],[1.2,2.3,2.1]),
    sub('Cách nạp ảnh phù hợp'),
    para('<b>UIT:</b> đọc label.json để ghép tên ảnh với nhãn. <b>VietHTR:</b> đọc shard theo state.json; '
         'giữ định danh source_shard/source_row và giải mã ảnh khi bộ nạp dữ liệu (DataLoader) cần. Có thể xuất ảnh ra đĩa một lần '
         'để dùng chung công cụ, nhưng đó là lựa chọn triển khai, không bắt buộc.'),
    box('<b>Trạng thái kho mã:</b> phần dùng chung được xếp trong src/common/; ba model có '
        'thư mục riêng trong src/models/. Các file mới chỉ là khung có chú thích để thành viên '
        'triển khai. Báo cáo đề xuất quy trình dữ liệu, chưa có pipeline huấn luyện hoàn chỉnh.'),
    para('Lưu ảnh dẫn xuất tại data/processed, manifest tại data/manifests, bảng mã tại data/vocab và nhật ký '
         'kiểm duyệt tại reports. Giữ đường dẫn tương đối với dự án để chuyển sang máy khác thuận tiện.'),
    small('Nguồn: [D1], [D2], cấu trúc tệp cục bộ [D4]. ID người viết không có thì để chưa biết, không suy ra từ số thứ tự ảnh.'))

page('Chia validation mà không làm sai đánh giá',
    para('<b>Validation</b> là tập dùng để chọn chiều cao ảnh, mức tăng cường, tỷ lệ lấy mẫu và thời điểm dừng. '
         'Cả hai nguồn hiện chưa có split validation trong bản đã phân tích. Đề xuất giữ nguyên toàn bộ test và '
         'tách khoảng 10% phần train cho validation; đây là mục tiêu tỷ lệ, số mẫu thực tế phụ thuộc nhóm.'),
    tbl(['Nguồn','Cách chia đề xuất','Giới hạn phải công bố'],[
        ['UIT','Ưu tiên giữ nguyên nhóm thư mục trong một phía train/val. Khoảng 25 trong 249 nhóm có thể làm điểm khởi đầu.','Thư mục chỉ là nhóm gần đúng; chưa xác nhận là người viết.'],
        ['VietHTR','Nếu tìm được metadata người viết/trang thì chia theo metadata. Nếu không, chia theo nhóm nội dung nhãn giống nhau đã chuẩn hóa.','Nhóm cùng nhãn ngăn trùng nội dung trực tiếp, không ngăn cùng người viết xuất hiện ở hai phía.'],
        ['Huấn luyện gộp','Tạo validation riêng của từng nguồn rồi ghép; giữ nhãn nguồn để chấm riêng.','Không để nguồn nhỏ biến mất trong validation tổng.'],
    ],[1,2.7,2.1]),
    para('<b>Group split - chia theo nhóm</b> giữ các mẫu có cùng mã nhóm ở cùng một phía. '
         'Trong GroupShuffleSplit, tỷ lệ chia được áp vào số nhóm chứ không trực tiếp vào số ảnh, '
         'vì các nhóm có thể lớn nhỏ khác nhau. [T4]'),
    para('Nếu phải đồng thời ràng buộc thư mục và nhãn giống nhau, có thể tạo nhóm liên thông rồi chia nhóm; '
         'cần kiểm tra nhóm quá lớn vì nhiều nội dung lặp có thể nối rất nhiều thư mục. Không ép bằng cách phá nhóm '
         'mà không ghi nhận thay đổi thiết kế.'),
    box('<b>Sau khi chia:</b> xác nhận không giao sample_id/hash pixel và không giao mã nhóm đã chọn; '
        'xây lại vocab chỉ từ train thực sự. Kiểm tra OOV validation; lưu seed 2026 (số khởi tạo '
        'cho phép chia ngẫu nhiên) cùng danh sách ID. '
        'Không điều chỉnh phép chia dựa vào việc điểm test tăng hay giảm.'),
    small('Nguồn: [D1], [D2] và [T4]. “Writer-independent” nghĩa là người viết ở train không xuất hiện ở validation/test; '
          'chưa có dữ liệu định danh để xác nhận tiêu chí này cho hai nguồn.'))

page('Resize ảnh: giữ tỷ lệ và bảo toàn dòng dài',
    para('<b>Resize</b> là thay đổi kích thước ảnh. Với chiều cao đích H và ảnh gốc W x h, giữ tỷ lệ bằng '
         '<b>W_mới = ceil(W x H / h)</b>; ceil là làm tròn lên. Đề xuất mốc đầu tiên H = 64 px. '
         'Ảnh cao 64 giữ nhiều vị trí theo chiều ngang hơn ảnh cao 32 khi giữ nguyên tỷ lệ.'),
    tbl(['Thông số từ train hiện tại','UIT','VietHTR'],[
        ['P99 chiều rộng ở H=32','649 px','744 px'],
        ['Chiều rộng lớn nhất ở H=32','911 px','1.312 px'],
        ['Chiều rộng lớn nhất ở H=64','1.821 px','2.624 px'],
        ['Vượt mức P95 train ở H=32 - train','4,74%','4,98%'],
        ['Vượt mức P95 train ở H=32 - test','0%','11,20%'],
    ],[2.9,1.2,1.2]),
    para('Nếu lấy 566 px là giới hạn cứng cho VietHTR tại H=32, 112/1.000 ảnh test vượt giới hạn đó. '
         'Đây là minh họa hậu quả của cắt ngang, không phải đề nghị chọn thông số bằng test. '
         'Quy tắc đầu vào phải chọn bằng train/validation và áp dụng nhất quán khi suy luận.'),
    sub('Quy tắc ảnh được đề xuất'),
    para('1. Chỉnh hướng hiển thị theo EXIF nếu có; EXIF là metadata có thể chứa hướng xoay ảnh. '
         '2. Kiểm tra/cắt lại lề hoặc vùng sai ở nhóm đã duyệt. '
         '3. Resize giữ tỷ lệ. 4. Thêm nền ở bên phải trong batch, không cắt đuôi dòng. '
         '5. Đưa giá trị ảnh về khoảng số thống nhất, thí dụ [0,1]; nếu dùng trung bình/độ lệch chuẩn, chỉ ước lượng trên train.'),
    box('<b>Ảnh rất dài:</b> đưa vào bucket riêng hoặc batch nhỏ hơn. Không ép mọi ảnh về cùng chiều rộng làm chữ méo. '
        'Nếu cần cắt thành đoạn, phải xác định nhãn đúng cho từng đoạn; không cắt ảnh ngẫu nhiên rồi giữ nguyên toàn bộ nhãn.'),
    small('Nguồn: [D1], [D2] width_caps_from_train.csv; chiều rộng H=64 được tính bổ sung từ sample_features.csv. '
          'Các số trên là trước khi cắt lại ảnh và trước khi tách validation, nên phải tính lại sau làm sạch.'))

page('CTC: vì sao số bước đầu ra phải đủ?',
    para('<b>CTC - Connectionist Temporal Classification</b> là hàm học cho chuỗi khi chưa biết từng ký tự nằm ở '
         'vị trí nào trong ảnh. Mạng tạo một chuỗi vị trí dự đoán theo chiều ngang. Ký hiệu <b>blank</b> của CTC '
         'là trạng thái không phát ký tự, khác với dấu cách có trong nhãn. [T2], [T3]'),
    box('<b>Điều kiện cần:</b> T ≥ L + R. T là số bước đầu ra; L là độ dài nhãn ký tự; R là số cặp ký tự '
        'liền kề giống nhau. Ví dụ “aa” có L=2, R=1 nên cần ít nhất 3 bước để có thể tách hai chữ a bằng blank. '
        'Đủ bước chỉ có nghĩa có thể căn chỉnh, không bảo đảm đọc đúng.'),
    *figure('ctc','Hình 9. Mô phỏng trên train: T = floor(W_mới / stride). Phải thay bằng công thức CNN thực tế khi triển khai.',185),
    tbl(['H / stride ngang','UIT train thiếu bước','VietHTR train thiếu bước'],[
        ['32 / 4','141 (2,006%)','191 (0,322%)'],
        ['32 / 8','6.164 (87,706%)','31.920 (53,876%)'],
        ['48 / 4','17 (0,242%)','16 (0,027%)'],
        ['64 / 4','8 (0,114%)','3 (0,005%)'],
    ],[1.7,1.8,1.8]),
    para('<b>Stride</b> là mức nhảy/giảm kích thước; stride ngang 8 tạo khoảng một bước đầu ra trên mỗi 8 pixel. '
         'Đề xuất bắt đầu H=64, stride ngang gần 4 và rà soát 11 mẫu train còn thiếu bước. '
         'Cả hai test hiện có 0 mẫu thiếu trong mô phỏng 64/4, nhưng đây không phải độ chính xác OCR.'),
    small('Nguồn: [D1], [D2], phép tính bổ sung report_ctc_height_scenarios.csv; nền tảng CTC [T2], [T3]. '
          'T phải tính từ vùng ảnh thật, trước padding batch; không tăng input_lengths giả bằng vùng nền để che lỗi.'))

page('Batch, padding và cách giảm lãng phí',
    *figure('padding','Hình 10. Mô phỏng H=32: UIT dùng 7.028 train; VietHTR dùng 20.000 train lấy mẫu cố định. Bucket sắp toàn cục là mốc lý tưởng.',205),
    para('<b>Batch</b> là nhóm ảnh xử lý trong một lượt. <b>Padding</b> là thêm nền để ảnh trong batch có cùng '
         'kích thước tensor - mảng số nhiều chiều đưa vào mạng. Nếu ghép ảnh rất ngắn với ảnh rất dài, ảnh ngắn phải mang nhiều nền thừa. '
         '<b>Bucketing</b> là xếp ảnh có chiều rộng gần nhau vào cùng nhóm để bớt padding.'),
    tbl(['Batch size = 32','UIT','VietHTR'],[
        ['Padding với batch ngẫu nhiên','32,88%','47,11%'],
        ['Padding khi sắp rộng lý tưởng','0,46%','0,33%'],
    ],[2.9,1.2,1.2]),
    para('Các con số lý tưởng là cận tham chiếu tiết kiệm trên mô phỏng, không phải lời hứa GPU sẽ nhanh hơn '
         'tương ứng. Trong train thật vẫn cần xáo trộn thứ tự ảnh và batch để tránh học theo độ dài tuần tự. '
         'GPU là bộ xử lý hỗ trợ các phép tính ma trận; lượng bộ nhớ thực còn phụ thuộc mô hình và chiều cao.'),
    box('<b>Collate - ghép batch:</b> đọc ảnh, resize giữ tỷ lệ, thêm nền phải theo ảnh rộng nhất; trả về ảnh, nhãn, '
        'chiều rộng thật và độ dài nhãn. Với CTC truyền input_lengths đúng CNN; với Transformer cần mask '
        '- mặt nạ chỉ vùng hợp lệ - phù hợp kiến trúc.'),
    para('Ở H=64 có thể thử các bucket trần rộng 384, 768, 1.152, 1.536, 2.048, 2.688 px; '
         'đây là gợi ý bao phủ train hiện tại, phải tính lại sau crop. Bắt đầu batch size 8-16, đo bộ nhớ, '
         'rồi tăng nếu ổn; không mặc định batch 64 sẽ phù hợp máy hiện tại.'),
    small('Nguồn mô phỏng: [D1], [D2] padding_simulation.csv. Phần giảm padding là tính toán diện tích nền, '
          'không phải benchmark tốc độ hay bộ nhớ đã chạy trên GPU.'))

page('Tăng cường dữ liệu mà không làm mất chữ',
    para('<b>Data augmentation - tăng cường dữ liệu</b> là tạo các biến thể ảnh trong lúc học, để mô hình '
         'không chỉ nhớ một điều kiện chụp. Chỉ áp dụng trên train; validation/test dùng đường xử lý xác định '
         'trước, không biến đổi ngẫu nhiên.'),
    tbl(['Biến đổi có thể thử','Mức khởi đầu đề xuất','Cần kiểm tra'],[
        ['Sáng / tương phản','Nhân khoảng 0,9-1,1','Ảnh tối vẫn còn đọc được; không cháy nền hoặc mất mực nhạt.'],
        ['Xoay nhẹ','Khoảng -1 đến +1 độ, có thể thử ±2','Mở rộng khung hoặc thêm nền để không cắt dấu.'],
        ['Tịnh tiến nhẹ','Khoảng 1-3 px ở ảnh đã resize','Nét lên cao và dấu chấm dưới vẫn nằm trong ảnh.'],
        ['Nhiễu / làm mờ nhẹ','Đặt mức nhỏ, xem trước bằng gallery','Dấu hỏi/ngã/chấm nặng không bị biến mất.'],
        ['Đen trắng bằng ngưỡng','Chỉ là một nhánh thí nghiệm riêng','Otsu có thể sai ở nền tối/dòng kẻ; không ghi đè ảnh nguồn.'],
    ],[1.25,1.7,2.4]),
    para('Các khoảng trên là <b>giả thuyết khởi đầu</b>, không được rút ra như mức tối ưu từ EDA. '
         'Trước khi train dài, tạo gallery trước/sau cho cả UIT và VietHTR, gồm ảnh ngắn, dài, mực nhạt, '
         'dấu dày và nền tối. Chọn mức biến đổi bằng kết quả validation.'),
    box('<b>Không dùng mặc định:</b> lật ngang, crop mất đoạn chữ, biến dạng quá mạnh, '
        'xóa nét mảnh hoặc biến đổi nhãn để đoán nội dung. Đổi ảnh nhưng vẫn giữ nhãn chỉ hợp lệ khi nội dung '
        'cần đọc còn nguyên và thứ tự ký tự không thay đổi.'),
    sub('Khi nào nên dùng ảnh xám?'),
    para('Ảnh xám là mốc đơn giản để giảm số kênh. Với dữ liệu có nhiều màu mực/nền, nên so sánh một nhánh RGB '
         '(ba kênh màu) và một nhánh xám trên cùng split. Chưa có phép thử mô hình để khẳng định nhánh nào tốt hơn.'),
    small('Căn cứ đề xuất: khác biệt sáng/tương phản [D1], đa dạng nền và ví dụ ảnh [D2], [D3]. '
          'Các mức biến đổi là quyết định thí nghiệm, không phải ngưỡng lọc chất lượng tự động.'))

page('Mô hình đầu tiên và cách kiểm tra pipeline',
    para('<b>Baseline - mốc tham chiếu</b> nên đủ đơn giản để phát hiện lỗi dữ liệu. Đề xuất CNN + BiLSTM + CTC: '
         'CNN trích đặc trưng nét từ ảnh; BiLSTM đọc chuỗi đặc trưng theo hai chiều; CTC học chuỗi ký tự '
         'mà không cần tọa độ từng chữ. Đây là lựa chọn triển khai ban đầu, chưa phải khẳng định mô hình tốt nhất.'),
    tbl(['Bước','Việc cần làm','Dấu hiệu đạt'],[
        ['1. Kiểm tra nhãn','Mã hóa rồi giải mã lại 100% nhãn train/val','Nhận lại đúng text_clean, không mất dấu hoặc ký tự lạ.'],
        ['2. Kiểm tra ảnh/batch','Hiển thị ảnh sau resize, nhãn và chiều rộng thật','Không méo chữ, không mất đuôi, chiều dài khớp công thức CNN.'],
        ['3. Chạy thử nhỏ (smoke test)','Chạy vài batch để kiểm tra luồng xử lý','Loss hữu hạn; dự đoán/nhãn/gradient không lỗi.'],
        ['4. Thử ghi nhớ tập nhỏ','Học trên 128-256 mẫu đã kiểm tra kỹ','CER train giảm rõ; nếu không, kiểm tra mã hóa/CTC/nhãn trước khi tăng mô hình.'],
        ['5. Chạy đầy đủ','Theo dõi CER validation theo từng nguồn','Lưu checkpoint tốt nhất theo quy tắc đã chọn trước.'],
    ],[1.1,2.4,2.1]),
    para('<b>Loss</b> là đại lượng mô hình tối ưu; <b>gradient</b> chỉ hướng cập nhật tham số; '
         '<b>checkpoint</b> là bản lưu trạng thái mô hình. Loss giảm không tự bảo đảm chữ dự đoán đúng, '
         'vì vậy phải đọc dự đoán và theo dõi CER - tỷ lệ lỗi ký tự.'),
    box('<b>CTC cần kiểm tra riêng:</b> blank không phải dấu cách; nhãn không chứa chỉ số blank; '
        'log_probs là logarit của xác suất dự đoán, phải đúng định dạng thư viện; '
        'input_lengths là độ dài đầu vào từng mẫu và không vượt T. '
        'zero_infinity có thể đặt loss vô hạn thành 0, nên không dùng để che mẫu thiếu bước; vẫn thống kê và sửa nguyên nhân. [T2]'),
    para('Chưa có thông tin GPU hoặc ngân sách chạy, nên không chốt learning rate '
         '(mức bước cập nhật tham số), số epoch hay batch tối ưu. '
         'Epoch là một lượt đi qua dữ liệu theo sampler; early stopping là dừng khi validation không cải thiện. '
         'Chỉ so sánh Transformer/MoE sau khi pipeline và mốc đơn giản đã ổn định.'),
    small('Nguồn kỹ thuật: [T2], [T3]. Phương án chạy nhỏ và kiến trúc mốc là đề xuất của báo cáo; '
          'chưa có thí nghiệm tốc độ, CER hoặc GPU nào được thực hiện trong tài liệu này.'))

page('Đánh giá: đo đúng và đọc lỗi cụ thể',
    box('<b>CER = (S + D + I) / N.</b> S là ký tự thay sai, D là ký tự bị thiếu, I là ký tự thừa, '
        'N là tổng ký tự nhãn chuẩn. Ví dụ nhãn “học”, dự đoán “hoc”: thay sai 1 trong 3 ký tự, CER = 33,33% '
        'nếu chấm sau NFC. CER có thể vượt 100% khi có nhiều ký tự chèn thừa. [T5]'),
    para('<b>WER - Word Error Rate</b> áp dụng khoảng cách sửa chuỗi lên các đơn vị từ/token. '
         'Nếu tách bằng dấu cách trong tiếng Việt, nên gọi rõ là WER theo token cách trắng; '
         '“sinh viên” là hai token theo quy tắc đó, dù có thể là một từ ghép. Không thay bộ tách giữa các thí nghiệm.'),
    tbl(['Báo cáo tối thiểu','Vì sao cần'],[
        ['CER/WER UIT và VietHTR riêng','Tránh nguồn lớn che đi kết quả kém trên nguồn nhỏ.'],
        ['CER gộp ký tự + trung bình CER hai nguồn','Gộp ký tự có trọng số theo số ký tự chuẩn; trung bình hai nguồn cho mỗi nguồn trọng số 1/2.'],
        ['Nhóm dòng ngắn / vừa / dài','Kiểm tra mất phần cuối và thiếu khả năng biểu diễn chuỗi dài.'],
        ['Nội dung đã gặp / chưa gặp trong train','Phân biệt nhận dạng chữ với lợi ích từ nội dung lặp.'],
        ['Dấu tiếng Việt, số và ký hiệu','Phát hiện lỗi nhỏ nhưng có thể đổi nghĩa.'],
        ['Gallery ảnh + nhãn + dự đoán','Biết lỗi từ crop, nhãn, mô hình hay quy tắc chấm.'],
    ],[2.2,3.2]),
    para('Tại EDA hiện tại, OOV ký tự test bằng 0 ở cả hai bộ. <b>OOV - Out Of Vocabulary</b> nghĩa là ký tự '
         'hoặc token chưa xuất hiện trong train. OOV token chữ là 1 loại ở UIT và 71 loại ở VietHTR; '
         'mô hình ký tự vẫn có thể ghép các chữ đã học để đọc token mới.'),
    para('Sau khi tách validation hoặc làm sạch, phải đo lại OOV. Giữ mọi mẫu test trong mẫu số chính; '
         'nếu báo thêm điểm trên tập con sạch, nêu rõ tiêu chí và số mẫu. Test UIT chỉ có 201 dòng, '
         'không suy ra độ tin cậy cao chỉ từ một điểm số hoặc p-value.'),
    small('Nguồn dữ liệu: [D1], [D2] oov_against_train.csv; định nghĩa khoảng cách sửa chuỗi: [T5]. '
          'Chưa có dự đoán mô hình nên báo cáo không đưa CER/WER thực nghiệm.'))

page('Ma trận thí nghiệm gọn và có đối chứng',
    tbl(['Mã','Thiết kế','Câu hỏi cần trả lời'],[
        ['E1','Chỉ train UIT; H=64, stride ngang gần 4','Mốc cho dữ liệu UIT sau làm sạch có hoạt động không?'],
        ['E2','Chỉ train VietHTR; cùng chính sách ảnh/nhãn','Mốc cho VietHTR và mức khác biệt điều kiện ảnh?'],
        ['E3','Gộp hai train theo tỷ lệ tự nhiên','Thêm nguồn khác có cải thiện trên từng test không?'],
        ['E4','Như E3, đổi duy nhất sampler sang khoảng 25/75','Giảm lệch số lượng có giúp UIT mà ít làm hại VietHTR?'],
        ['E5 - sau đó','Như mốc tốt, thay H=64 bằng H=48 sau audit CTC','Có tiết kiệm tài nguyên với mức lỗi chấp nhận được?'],
        ['E6 - sau đó','Bật/tắt augmentation nhẹ, giữ các phần khác','Biến đổi có giúp tổng quát hóa hay làm mất dấu?'],
    ],[.65,2.5,2.25]),
    para('<b>Ablation - thử bỏ/thay từng thành phần</b> giúp biết cải thiện đến từ đâu. '
         'Không đồng thời đổi cách chia validation, vocab, ảnh, sampler và mô hình rồi quy hết kết quả cho một yếu tố. '
         'Kết quả chính chỉ chọn sau khi quy trình chọn mô hình đã được cố định trên validation.'),
    para('Với huấn luyện gộp, nên chọn checkpoint theo trung bình CER validation của hai nguồn nếu muốn '
         'coi chúng quan trọng ngang nhau; đồng thời công bố điểm từng nguồn và điểm gộp. '
         'Nếu mục tiêu ứng dụng ưu tiên một nguồn khác, đặt trọng số trước khi xem test.'),
    box('<b>Sổ thí nghiệm cần lưu:</b> mã nguồn/commit, phiên bản manifest, seed, quy tắc nhãn, bảng mã, '
        'H và công thức output length, augmentation, sampler, batch size, số bước cập nhật, tài nguyên và checkpoint. '
        'Với sampler lấy lặp, số epoch không còn đủ để so sánh công bằng; phải ghi cả lượt mẫu và bước cập nhật.'),
    para('Sau E1-E4, mới cân nhắc pretrain - học trước trên dữ liệu lớn - rồi fine-tune - điều chỉnh tiếp '
         'trên miền đích - hoặc thử Transformer/MoE. Mỗi bước thêm chỉ hợp lý khi có câu hỏi rõ và validation '
         'cho thấy mốc hiện tại còn hạn chế tương ứng.'),
    small('Các thiết kế E1-E6 là đề xuất; chưa có kết quả chứng minh mô hình hoặc cấu hình nào tốt hơn. '
          'Không gộp nhãn/ảnh test vào pretrain hoặc fine-tune.'))

page('Điều kiện dữ liệu sẵn sàng để train',
    tbl(['Hạng mục nghiệm thu','Hiện trạng từ EDA','Việc cần hoàn tất'],[
        ['Đủ cặp ảnh-nhãn','67.476 cặp mở được; 44 ảnh UIT chưa có nhãn','Giữ 44 ảnh ở trạng thái chờ, hoặc bổ sung nhãn được duyệt.'],
        ['Nhãn một dòng nhất quán','15 nhãn điều khiển; 1 NFC thay đổi; 132 khoảng trắng lặp','Duyệt tab/xuống dòng và tạo nhật ký chuẩn hóa.'],
        ['Crop đúng vùng nội dung','Đã thấy lề lớn, trang trí, nhiều dòng và hàng lân cận','Rà soát ưu tiên theo gallery; sửa/tách/cách ly có lý do.'],
        ['Có validation riêng','Chưa có split trong nguồn hiện tại','Chia từ train theo nhóm, lưu ID và seed; đo lại OOV.'],
        ['Nhãn mã hóa được','Vocab hiện tại phủ test gốc','Xây vocab từ train sau chia; kiểm tra encode/decode.'],
        ['CTC đủ bước với CNN thật','Mô phỏng H=64/4 còn 11 mẫu train thiếu bước','Xử lý mẫu; kiểm tra bằng output length thật trước train dài.'],
        ['Không rò rỉ ảnh chính xác','Không thấy hash pixel giao split/hai nguồn','Kiểm tra lại trên bản sau crop và chia validation.'],
        ['Đánh giá có thể tái lập','EDA và nguồn đã lưu','Lưu quy tắc chấm, config, manifest, dự đoán và checkpoint.'],
    ],[1.35,1.9,2.4]),
    box('<b>Thứ tự triển khai khuyến nghị:</b> khóa dữ liệu gốc → kiểm duyệt → tạo manifest sạch → chia train/val '
        '→ xây vocab → triển khai resize/bucket → kiểm tra CTC và tập nhỏ → train đầy đủ → chấm test cuối cùng.'),
    para('Sau làm sạch, chạy lại các thống kê để có số mẫu dùng thật theo từng lý do giữ/loại. '
         'Không công bố một con số “đã làm sạch” khi mới chỉ đánh cờ. Một mẫu còn chờ kiểm duyệt không nhất thiết '
         'là mẫu xấu; đó là trạng thái chưa đủ bằng chứng để quyết định.'),
    small('<b>11 mẫu ưu tiên theo mô phỏng H=64/4:</b> UIT: train/12/6.jpg, train/161/33.jpg, '
          'train/215/43.jpg, train/220/27.jpg, train/224/22.jpg, train/65/20.jpg, train/9/24.jpg, train/91/1.jpg. '
          'VietHTR: train/0014900, train/0018408, train/0035761. '
          'Bảng kèm nhãn và số bước: reports/results/eda/report_ctc_review_candidates_H64_S4.csv.'),
    small('Đây là danh sách nghiệm thu đề xuất. Báo cáo chỉ đọc và phân tích dữ liệu; chưa tự sửa nhãn, '
          'tách split mới, loại mẫu hoặc huấn luyện mô hình.'))

page('Từ điển dễ hiểu - dữ liệu và thống kê',
    tbl(['Thuật ngữ','Giải thích theo ngữ cảnh báo cáo'],[
        ['EDA','Phân tích khám phá: xem cấu trúc, phân bố và những điều bất thường trước khi học mô hình.'],
        ['Sample / label / annotation','Mẫu / nhãn / thông tin gán nhãn. Ở đây một mẫu là một ảnh và đoạn chữ tương ứng.'],
        ['Split','Một phần dữ liệu. Train để học; validation để chọn cấu hình; test để chấm cuối cùng.'],
        ['Metadata / provenance','Thông tin kèm dữ liệu / nguồn gốc. Ví dụ người viết, trang gốc, cách thu thập, giấy phép.'],
        ['Shard / Arrow / bytes','Phần tệp dữ liệu / định dạng lưu bảng / dữ liệu nhị phân của ảnh.'],
        ['Median / mean','Trung vị / trung bình. Trung bình nhạy với giá trị cực lớn hơn trung vị.'],
        ['Quantile / percentile','Phân vị: mốc phần trăm mẫu không vượt quá, ví dụ P95.'],
        ['Histogram / density','Biểu đồ chia khoảng / mật độ. Histogram mật độ có tổng diện tích bằng 1, không phải tổng số ảnh.'],
        ['ECDF','Đường phân phối tích lũy thực nghiệm: ở x có bao nhiêu phần trăm mẫu không vượt x.'],
        ['IQR / outlier','Khoảng Q3-Q1 / điểm ngoài phạm vi thông thường. Điểm ngoài hàng rào IQR chưa chắc là lỗi.'],
        ['Skewness / kurtosis','Mức lệch trái/phải / mức nặng đuôi: có nhiều giá trị rất xa trung tâm hay không. Không tự suy ra chất lượng ảnh.'],
        ['CV','Độ lệch chuẩn mô tả độ phân tán quanh trung bình. CV chia giá trị đó cho trung bình để so mức biến thiên tương đối.'],
        ['KS D / p-value','KS D đo mức khác nhau của hai phân phối. p nhỏ gợi ý khác biệt nếu giả định kiểm định đúng; không cho biết khác biệt lớn đến đâu.'],
        ['Spearman / correlation','Tương quan theo thứ hạng / mức liên hệ. Hai biến cùng tăng không chứng minh biến này gây biến kia.'],
        ['Long tail / Zipf','Nhiều loại hiếm và ít loại phổ biến / quan hệ hạng-tần suất thường được xem bằng trục log.'],
        ['Gini / entropy','Gini cao: tần suất dồn vào ít loại. Entropy cao: tần suất phân tán hơn. Phải ghi rõ tập loại và mẫu số.'],
    ],[1.65,3.75]),
    small('Một số thuật ngữ được dùng trong notebook dù không phải chỉ số quyết định trực tiếp trong PDF. '
          'Các phép mô tả phân phối không thay thế việc đọc ảnh và kiểm tra nhãn.'))

page('Từ điển dễ hiểu - xử lý và mô hình',
    tbl(['Thuật ngữ','Giải thích thực hành'],[
        ['NFC / code point','Chuẩn hóa Unicode dạng ghép / đơn vị mã Unicode. Giúp hai cách mã hóa tương đương được so sánh nhất quán.'],
        ['Vocab / OOV','Bảng mã ký tự/token / phần tử chưa có trong bảng mã train.'],
        ['Resize / crop / aspect ratio','Đổi kích thước / cắt vùng ảnh / tỷ lệ rộng-cao. Crop sai có thể làm mất chữ.'],
        ['Foreground / background / Otsu','Phần ước lượng là mực / nền / cách tự chọn ngưỡng tách sáng tối.'],
        ['Proxy / flag / review','Đại lượng đại diện / cờ gợi ý kiểm tra / xem xét thủ công. Chưa phải nhãn chất lượng chắc chắn.'],
        ['Hash / dHash / duplicate','Mã băm / băm hình thái rút gọn / bản sao. Cùng dHash chỉ là ứng viên.'],
        ['Manifest / deterministic','Danh mục mẫu có nhãn và vị trí / chạy lại cùng đầu vào cho cùng kết quả.'],
        ['Domain / distribution shift','Miền dữ liệu / phân bố thay đổi giữa các nguồn hoặc train-test.'],
        ['Batch / collate / padding','Nhóm mẫu / thao tác ghép nhóm / thêm nền để thống nhất kích thước tensor.'],
        ['Bucket / sampler / mask','Nhóm độ rộng gần nhau / cách chọn mẫu / vùng đánh dấu vị trí hợp lệ.'],
        ['CTC / blank / stride','Học chuỗi chưa căn vị trí / trạng thái không phát ký tự / mức giảm bước theo chiều ngang.'],
        ['log_probs / input_lengths','Dạng xác suất mà CTC yêu cầu để tính loss ổn định / số bước đầu vào thật của từng mẫu, trước nền padding batch.'],
        ['CNN / BiLSTM / Transformer','Mạng trích đặc trưng ảnh / mạng đọc chuỗi hai chiều / mạng cân nhắc thông tin giữa nhiều vị trí.'],
        ['Loss / gradient / epoch','Đại lượng tối ưu / hướng cập nhật tham số / lượt đi qua dữ liệu theo cách chọn mẫu.'],
        ['Overfit / checkpoint / early stopping','Học quá sát train / bản lưu mô hình / dừng theo chất lượng validation.'],
        ['Baseline / ablation','Mốc tham chiếu / thí nghiệm bỏ hoặc đổi riêng từng thành phần.'],
        ['CER / WER / inference','Tỷ lệ lỗi ký tự / lỗi token-từ theo quy tắc tách / chạy mô hình để dự đoán ảnh mới.'],
        ['Pretrain / fine-tune / MoE','Học trước / học điều chỉnh tiếp / mô hình có nhiều nhánh chuyên gia và cơ chế chọn nhánh tính cho từng đầu vào.'],
    ],[1.7,3.7]),
    small('Thuật ngữ được giải thích theo bài toán nhận dạng chữ viết tay một dòng; không phải mô tả toàn bộ '
          'các biến thể kiến trúc hoặc mọi thiết lập huấn luyện.'))

page('Nguồn, tệp đối chiếu và phạm vi kết luận',
    sub('Bằng chứng cục bộ - số liệu của đúng bản dữ liệu đang có'),
    para('<b>[D1]</b> notebooks/eda/EDA_UIT_HWDB_line.ipynb và reports/results/eda/UIT_HWDB_line/. '
         '<b>[D2]</b> notebooks/eda/EDA_viet_htr.ipynb và reports/results/eda/viet_htr/. '
         '<b>[D3]</b> ảnh gốc tại data/UIT_HWDB_line/ và các hàng ảnh trong data/viet_htr/. '
         '<b>[D4]</b> cấu trúc src/, scripts/ và README.md tại thời điểm tạo báo cáo.'),
    tbl(['Cần kiểm tra điều gì?','Tệp nguồn tương ứng trong thư mục EDA'],[
        ['Số mẫu, lỗi nguồn, độ phủ ảnh','summary.json; source_inventory.csv; source_issues.csv; image_coverage.csv'],
        ['Đặc trưng và vị trí từng mẫu','sample_features.csv; flagged_labels.csv; image_errors.csv'],
        ['Phân phối, OOV và trùng lặp','distribution_shift.csv; oov_against_train.csv; duplicate_summary.csv; cross_dataset_overlap.csv'],
        ['Resize / CTC / padding','width_caps_from_train.csv; ctc_feasibility_simulation.csv; padding_simulation.csv'],
        ['Phép tính bổ sung của PDF','report_ctc_height_scenarios.csv; report_ctc_review_candidates_H64_S4.csv; report_evidence.json ở reports/results/eda/'],
    ],[1.7,3.6]),
    sub('Tài liệu kỹ thuật gốc - đối chiếu ngày 01/11/2026'),
    para('[T1] <link href="https://www.unicode.org/reports/tr15/" color="#216A91">Unicode: UAX #15, Unicode Normalization Forms</link>. '
         'Cơ sở phân biệt chuẩn hóa NFC và tương thích NFKC.'),
    para('[T2] <link href="https://docs.pytorch.org/docs/2.9/generated/torch.nn.CTCLoss.html" color="#216A91">PyTorch: CTCLoss</link>. '
         'Định dạng đầu vào, blank, độ dài chuỗi và zero_infinity.'),
    para('[T3] <link href="https://www.cs.toronto.edu/~graves/icml_2006.pdf" color="#216A91">Graves và cộng sự, ICML 2006: Connectionist Temporal Classification</link>. '
         'Nghiên cứu gốc về học chuỗi không cần căn chỉnh ký tự.'),
    para('[T4] <link href="https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html" color="#216A91">scikit-learn: GroupShuffleSplit</link>. '
         'Chia theo nhóm, với tỷ lệ áp dụng lên số nhóm.'),
    para('[T5] <link href="https://jitsi.github.io/jiwer/" color="#216A91">JiWER: tài liệu các chỉ số CER/WER</link>. '
         'Đo lỗi dựa vào khoảng cách sửa chuỗi.'),
    box('<b>Giới hạn:</b> số liệu mô tả đúng các bản cục bộ đã quét; chưa kiểm duyệt toàn bộ nhãn bằng mắt, '
        'chưa xác nhận người viết/giấy phép và chưa có kết quả huấn luyện. Không suy ra độ khó, chất lượng mô hình '
        'hoặc tính độc lập của nguồn chỉ từ số mẫu và hash.'),
    small('Có thể tái tạo báo cáo bằng scripts/build_eda_pdf_report.py sau khi chạy hai notebook. '
          'Nếu dữ liệu hoặc quy tắc làm sạch thay đổi, cần chạy lại EDA, cập nhật nhận xét và kiểm tra lại trang PDF.'))

class ReportDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        key=getattr(flowable,'_bookmarkName',None)
        if key:
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0,closed=False)

def background(canvas,doc):
    canvas.saveState()
    canvas.setFillColor(NAVY);canvas.rect(0,PAGE_H-38,PAGE_W,38,fill=1,stroke=0)
    canvas.setFont('Body-Bold',8);canvas.setFillColor(colors.white)
    canvas.drawString(48,PAGE_H-24,'DỮ LIỆU CHỮ VIẾT TAY | PHÂN TÍCH VÀ CHUẨN BỊ HUẤN LUYỆN')
    canvas.setStrokeColor(colors.HexColor('#CAD8E0'));canvas.line(48,40,PAGE_W-48,40)
    canvas.setFont('Body',8);canvas.setFillColor(MUTED)
    canvas.drawString(48,26,'UIT_HWDB_line / viet_htr - 01.11.2026')
    canvas.drawRightString(PAGE_W-48,26,f'{doc.page} / {len(PAGES)}')
    canvas.restoreState()

pdf_path=OUTPUT/'Bao_cao_EDA_va_de_xuat_huan_luyen_chu_viet_tay.pdf'
HEIGHT=PAGE_H-65-47
doc=ReportDoc(str(pdf_path),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=65,bottomMargin=47,
    title='Phân tích chi tiết UIT_HWDB_line và viet_htr - Đề xuất chuẩn bị huấn luyện',
    author='Báo cáo từ dữ liệu EDA cục bộ',pageCompression=1,allowSplitting=0)
doc.addPageTemplates(PageTemplate(id='report',frames=[Frame(48,47,WIDTH,HEIGHT,
    leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=background))
story=[]
for number,(title,flows) in enumerate(PAGES,1):
    height=0
    for flow in flows:
        _,h=flow.wrap(WIDTH,HEIGHT)
        height+=h+flow.getSpaceBefore()+flow.getSpaceAfter()
    print(f'Page {number:02d}: estimated {height:.1f}/{HEIGHT:.1f} pt - {title}',flush=True)
    if height>HEIGHT+1:
        raise ValueError(f'Page {number} planned content is too tall: {height:.1f} > {HEIGHT:.1f}')
    if story:story.append(PageBreak())
    story.extend(flows)
doc.build(story)

evidence={'report_date':'2026-11-01','timezone':'Asia/Bangkok','datasets':{},'ctc_simulation':CTC.to_dict('records'),
          'pdf_pages_planned':len(PAGES),'pdf_path':str(pdf_path.relative_to(ROOT)),
          'notes':'PDF combines measured full-dataset EDA, visually reviewed examples, and proposed training policies; no training performed.'}
for name in NAMES:
    f=FRAMES[name]
    source=EDA/name/'sample_features.csv'
    evidence['datasets'][name]={'summary':SUMMARY[name],'features_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'control_tab_lines':int(f.text_raw.str.contains('\t',regex=False).sum()),
        'control_newline_lines':int(f.text_raw.str.contains('\n',regex=False).sum()),
        'test_lines_seen_content_train':int((f.split.eq('test')&f.text_compare.isin(set(f.loc[f.split.eq('train'),'text_compare']))).sum())}
(EDA/'report_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print('PDF:',pdf_path,flush=True)
