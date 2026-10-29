---
name: aurora-product-photos
description: Aurora Cigars 网站产品照片的标准和上新流程：清点用户 Mac 上的照片 → 逐张看图对上产品（文件名 + 环标 + 雪茄长宽比）→ 生成带指纹的对照表 → 新款建草稿 → 上传（白底正方形、雪茄横放、去 EXIF）→ 用诊断包验收 → 给用户一个可核对的对照页面。用户说「把这些雪茄照片放到网站上」「热门款的照片」「换产品图」「照片配错了」「图是歪的 / 竖的」「新到了一批限量」，或者发来 aurora-图片清单.zip 时，都用这个流程。Use for any product photo work on the Aurora Cigars site.
---

# Aurora 产品照片：标准与上新流程

照片在用户自己的 Mac 上（访达里的文件夹，文件名多是中文型号名，例如「高希霸 世纪 三.PNG」「2018年潘趣 香港地区限量 邓爵士.PNG」）。
云端连不上网站，所以流程是：用户运行脚本清点 → 我们核对、写对照表、推到仓库 → 用户运行脚本上传 → 用户发回诊断包验收。

## 照片在网站上的标准

- **主图**：单支雪茄侧面照，白底正方形，雪茄**横放**在正中，两端各留约 6% 白边。上传脚本自动做（`aurora_setup.py` 的 `prepare_photo`）：
  长宽比超过 2 的横条图补成正方形、转 JPG、长边不超过 2000px。商品卡和产品页都是正方形框、WooCommerce 缩略图也按正方形裁，横条图不补边就只剩中间一截。
- **图集**：整盒、开盒、细节照放第二张起（role 写「包装 / 本体 / 细节 / 其他」）。
- **去 EXIF**：上传前去掉 EXIF（含方向标记和拍摄地点），像素不动。这批照片里每张都带着错误的「旋转 90°」标记，
  WordPress 会照着它把图转歪并在文件名后加 `-rotated`。所以**核对时看原始像素**（Pillow 默认不按 EXIF 旋转，正好就是上传后的样子）；
  原始像素本身是歪的照片要单独标出来，别上传。
- 文件名按 SKU（`CUB-021.jpg`、图集 `CUB-068-2.jpg`），alt 和标题是产品名。原图永远不改，处理都在副本上。

## 流程

### 1. 清点（只读）
请用户在 Mac 终端运行（应用密码用户自己填），提示时**一次只拖一个文件夹**——两个文件夹里常有同名照片：
```
cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/<分支>.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='应用密码' bash kinglogan-<分支>/aurora-cigars/scripts/run_photos.sh
```
桌面上会生成 `aurora-图片清单.zip`：`manifest.csv`（编号、文件、尺寸、sha1 指纹、内容重复的文件）、`thumbs/`（长边 1000px 缩略图）、
`products.json`（网站全部产品的当前名称、状态、图片来源）。同时在桌面备份了所有产品的现有图片。解压到一个新的空目录里再用。

### 2. 逐张核对
```bash
S=.claude/skills/aurora-product-photos/scripts
python3 $S/contact_sheet.py <清点包> <输出目录>                 # 每 20 张一页，带编号和文件名
python3 $S/contact_sheet.py <清点包> <输出目录> --only 121,142,70  # 放大看拿不准的几张
python3 $S/ratios.py <清点包> 164,168,90 [--brand Trinidad]      # 量长宽比，和 references/vitolas.md 里的常见型号对照
```
每张都要**看图**，不能只看文件名。判断依据按可靠程度：环标上的字（OPEN SLAM、MAGNUM 56、EDICIÓN LIMITADA 2024、EXCLUSIVO LIBANO）>
文件名里的型号 > 雪茄长宽比（同品牌里比，猪尾和阴影会让比例偏大，相差 10% 内算接近）> 排除法。

中文文件名的常见对应（都在这批照片里出现过）：世纪 = Siglo，半世纪 = Medio Siglo，长矛 = Lanceros，贝伊可 = Behike；
艾蒙多 = Edmundo，满贯 = Open Slam，老鹰 = Open Eagle；鉴赏家 = Connoisseur，玛瑙 = Magnum，特许 = Regalías；
逍遥 = Epicure，赛科 = Río Seco；比利高 = Belicosos；创建 = Fundadores，殖民地 = Coloniales，维格 = Vigía，露娜 = Media Luna，
拖佩斯 = Topes，特罗那 = La Trova，艾斯梅那达 = Esmeralda；小息 = Entretiempos；挚爱 = Favoritas；英勇 = Galanes，斗牛士 = Picadores；
比亚达 = José L. Piedra，猎人 = Cazadores；腓尼基 = Phoenicia，黎巴嫩 = Líbano（地区限量）。

**踩过的坑**：按文件名自动比对会把「世纪一」配成「半世纪」、「鉴赏家2号」配成「2号」——中文逐字相似度不可靠，一律人工核对。
「鉴赏家2号」≠「2号」、「玛瑙56 全球限量 2015」≠「玛瑙56 瓷罐」：同型号的限量版、特级珍藏版、LCDH 版都不是常规款，不能拿来当常规款的图。

每张照片的结论分四类：
- **确认**：文件名或环标直接对应站上的产品。
- **推断**：名字对不上但有充分依据（比例 + 排除法），也上传，note 以「推断：」开头写明依据，列给用户核对。
- **待确认**：有候选但拿不准、或认不出型号——不上传，写清楚候选和疑点。
- **不上传**：重复文件、站上没有且不新建的产品（保湿盒、礼盒等，除非用户要）。

站上没有、但用户要上架的（地区限量、年度限量）：写进 `aurora-cigars/content/new-products.csv`（sku 用 `LTD-` 续号、name 用文件名原文、
categories 用分类 slug，如 `collection|punch-collection|limited-editions`），同时加到 `content/name-review.csv` 标红，
运行时由 `create-drafts` 建成**草稿**（无价格、规格），等用户补资料后发布。不要编造英文官方名、价格和规格。

### 3. 生成对照表
把结论写成 `decisions.json`（格式见 `scripts/make_mapping.py` 开头），然后：
```bash
python3 $S/make_mapping.py <清点包> decisions.json aurora-cigars/content/photo-mapping-<批次>.csv --new-products aurora-cigars/content/new-products.csv
```
脚本会检查 SKU 存在、每款只有一张主图、重复文件没有被重复上传，并给每行带上清点时的 sha1——上传时按指纹认出核对过的那一张。

**每批照片一份对照表**：第一批（访达文件夹「1211」）是 `content/photo-mapping.csv`，之后的用 `photo-mapping-<批次>.csv`
（例如 `photo-mapping-热门2.csv`），不要改写已上线批次的文件。上传时脚本会读所有 `photo-mapping*.csv`：已经配好的产品直接跳过
（不需要再拖它的照片），照片不在这次拖进来的文件夹里的产品跳过并列出来，所以用户每次只拖新的那个文件夹就行。
同一款产品不要在两批里都给主图——新照片要替换旧图时，改旧批次那一行的 status 为「不上传」并在 note 里写明原因。

### 4. 给用户看对照页
```bash
python3 $S/review_page.py aurora-cigars/content/photo-mapping-<批次>.csv <清点包> <scratch>/aurora-photo-mapping-<批次>.html --source "访达文件夹「热门 2」"
```
用 Artifact 发布：每批一个页面；同一批改了结论就用同一个文件路径（或 url）重新发布，保持同一个链接。第一批的页面是
https://claude.ai/artifact/RsBHR1ojDCoAfJhp2DHqN3 。页面按「推断 / 待确认 / 直接对应 / 新建草稿 / 不上传」分组，用户看图就能核对。

### 5. 上传
提交推送后，请用户运行同一条命令把末尾换成 `run_photos.sh auto`（同样一次拖一个文件夹）：清点备份 → 更新插件 → 改名 → 合并重复 → 草稿去重 →
新建草稿 → 标红 → 按对照表上传 → 导出 `aurora-audit-配图后.zip`。每一步可重复运行：已做好的会跳过，上传每 10 款保存一次，单张失败不影响其他。
上传处理方式变了（例如这次去 EXIF）就把 `aurora_setup.py` 里的 `PHOTO_PREP` 加 1，重新运行时旧方式传的照片会重传。

### 6. 验收
用发回的诊断包检查（`report.json`）：
- `image_check.broken` 为空；
- 照片产品的 `meta.aurora_photo_files` 和对照表一致、`meta.aurora_photo_prep` 是当前版本、`image_srcs` 里没有 `-rotated`；
- 产品总数、上架/草稿数量符合预期；新建的都是草稿。
再告诉用户：多少款配了图、多少张、哪些待确认、哪些推断请核对，并附对照页链接。

## 常用撤销
- `run_photos.sh restore ~/Desktop/aurora-产品图片备份-<时间>.json`：恢复备份时的名称、图片、上下架状态。
- `run_photos.sh cleanup`：删除没有产品在用的旧 `-rotated` 图（会永久删除，先确认用户同意）。
