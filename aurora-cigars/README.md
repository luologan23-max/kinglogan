# Aurora Cigars 网站

迪拜古巴雪茄询价型网站：WordPress + WooCommerce（只当产品库用），所有成交都走 WhatsApp。

- 站点：https://wordpress-1627597-6431471.cloudwaysapps.com（Cloudways）
- 公司：Aurora Global Tobacco Trading FZCO（JAFZA, Dubai）
- WhatsApp：+971 585598868

## 目录

| 路径 | 作用 |
|---|---|
| `plugin/aurora-core/` | 网站功能插件（见下文） |
| `dist/aurora-core.zip` | 打包好的插件，直接上传到 WP 后台 |
| `scripts/aurora_setup.py` | 一键配置 WooCommerce、导入产品、创建页面和导航 |
| `content/catalog.csv` | 80 款标准型号目录（10 个品牌常规款，规格齐全，价格空着 = 显示「请询价」），由 `tools/build_catalog.py` 生成 |
| `content/brands.json` | 10 个品牌的中英文介绍（顺序 = 首页品牌宫格顺序） |
| `content/pages/*.html` | 首页、关于、防伪查验、常见问题、批发合作、配送与条款 |
| `content/images/*.jpg` | 10 个品牌 + Aurora 通用的产品图（1600×1600，自行渲染，无版权问题） |
| `tools/render_cigar.html`、`tools/render_all.js` | 品牌产品图渲染器，改了品牌后运行 `node tools/render_all.js` 重新出图 |
| `scripts/run_all.sh` | Mac 一键上线（见下文） |
| `scripts/run_fix.sh` | Mac 一键设计修复：更新插件、清理、恢复原有页面、重复型号改草稿、导出诊断包 |
| `scripts/build_zip.sh` | 修改插件后重新打包 |
| `scripts/run_site.sh` | Mac 一条命令：`audit` 只读导出诊断包；`update` 更新插件后导出诊断包 |
| `scripts/run_photos.sh` | Mac 一条命令：照片清点、按对照表上传、清理旧图、撤销（见下文「产品实拍图」） |
| `tests/fetch_vendor.sh` | 下载离线还原页面要用的 jQuery 等前端库 |
| `tests/` | 测试（模拟环境渲染、浏览器交互、模拟 WooCommerce API、用诊断包离线还原线上页面） |

## aurora-core 插件做了什么

插件有两种前台模式，在「Aurora 设置」里的「整合模式」切换（默认 auto，自动判断）：

- **整合模式**：站点已经有自己的店面代码片段（Code Snippets 里的 v6 商品卡、产品页 v4、全局导航/页脚）时自动启用。店面外观完全交给站点自己的设计，插件只做三件事：
  1. 输出站点的设计系统 CSS 片段（片段 11，原来因为作用域是 site-css 而一直没有输出到页面）
  2. 隐藏和站点设计重复的层：Astra 默认的卡片标题/价格/购物袋按钮、旧需求单脚本加的角标和蓝色按钮、重复的面包屑和页脚、产品页上的悬浮 WhatsApp
  3. 修好站点自带的「＋」和「加入询价清单」按钮（原来 onclick 里的引号把属性截断了，点了没反应），并把旧的数组格式清单统一成需求单页面读取的 `{items:[…]}` 格式
- **店面模式**：没有这些片段时使用下面这一整套插件自带的店面
- **站点原有的手写页面**（首页「HOMEPAGE v4」、关于、腓尼基限量等整段手写 HTML 的页面，两种模式都适用）：跳过 WordPress 的自动分段和排版美化（它们会在手写 HTML 里插满 `<p>`/`<br>`，拆散卡片、打乱网格，还把页内多语言脚本里的 `&&` 改坏），并加载 `aurora-pages.css`：补上首页各区块和 `aurora-btn-*` 按钮丢失的样式，隐藏重复的滚动条和页面标题。区块编辑器的页面和本插件建的页面不受影响。页面里粘贴的 PHP 代码（WordPress 不会执行，原样显示成乱码）会被去掉；「年度限量」页那段产品查询按原意输出：限量分类有产品时列出产品，没有时显示页面原来的「配额已关闭」提示
- **「Request a Quote」页**：只剩一个已停用的 YITH 询价短代码，旧链接转到站点自己的需求单页面 `/my-request/`

两种模式都保留：目录模式、年龄验证、内部预览模式、「价格请询价」、短代码。

- **目录模式**：产品不可购买，购物车和结账页跳回商店，列表页按钮改成「查看详情 · 询价」，去掉头部购物车图标
- **产品详情页**：手机首屏顺序为 图片 → 品牌 → 名称 → 现货 / 防伪 / 限量标签 → 价格 → 盒数选择 → WhatsApp 一键询价 → 加入询价清单；规格表和配送说明放到下方标签页
- **WhatsApp 询价消息**
  - 普通款：`您好，我想询价：{产品名} {规格}，USD {价格}/盒，请确认库存。` 后面带上「数量：N 盒」
  - 限量版：`您好，我对 {产品名} 感兴趣，请确认库存与价格。`
- **询价清单**：客户可以挑多款、改盒数，然后整单一次发到 WhatsApp，消息里带参考合计。清单存在客户自己的浏览器里，所以不再需要 YITH Wishlist
- **悬浮 WhatsApp 按钮**：右下角，#25D366，48×48px，所以也不需要 Click to Chat 插件
- **年龄验证**：21 岁，记住 30 天，弹窗里写明不发货地区
- **设计**：黑白金配色；标题用 Bodoni Moda，正文用 EB Garamond，按钮用 Jost
- **商店列表**：卡片显示品牌和规格，顶部有品牌筛选条，没有产品图时用统一的品牌占位图
- **页脚**：公司信息、联系方式、服务链接、年龄和发货限制（Astra 主题自动显示）
- **短代码**（可放进 Elementor 的「短代码」小部件）：
  - `[aurora_brands limit="6"]` 品牌宫格
  - `[aurora_whatsapp text="WhatsApp 咨询" message="您好"]` WhatsApp 按钮
  - `[aurora_shipping]` 配送说明
  - `[aurora_products limit="8" brand="cohiba"]` 精选产品
  - `[aurora_brand_nav]` 品牌筛选条
  - `[aurora_footer]` 页脚（不用 Astra 时）
- **内部预览模式**（默认开启）：没登录后台的访客只能看到「即将上线」页面，整站对搜索引擎 noindex。在「Aurora 设置」页面可以复制「预览分享链接」，发给朋友看效果用。正式上线时把「内部预览模式」改成 0
- **没填价格的产品**显示「价格请询价」，询价消息改为「请告知价格与库存」
- **后台设置**：WooCommerce → Aurora 设置，可以改 WhatsApp 号码、年龄、不发货地区、物流文案

## 一键上线（推荐，在自己的 Mac 上运行）

打开「终端」，粘贴下面这条命令（把密码换成你在后台生成的 Application Password）：

```bash
cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/claude/minimax-model-setup-dfLij.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx' bash kinglogan-claude-minimax-model-setup-dfLij/aurora-cigars/scripts/run_all.sh
```

`run_all.sh` 会依次完成这些：安装并启用插件（借助站点上的 Code Snippets 临时建一个只有管理员能调用的安装接口，装完自动删除）→ 店铺设置 → 停用多余插件 → 导入 80 款 → 配品牌图 → 建页面（站点原有的同名页面保留不动，只补上缺的）→ 建导航 → 输出预览分享链接。

## 一键设计修复（插件 1.0 已经装过时用）

```bash
cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/claude/minimax-model-setup-dfLij.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx' bash kinglogan-claude-minimax-model-setup-dfLij/aurora-cigars/scripts/run_fix.sh
```

`run_fix.sh` 依次：把插件更新到 1.1（整合模式）→ 删除遗留的临时安装片段、停用多余插件 → 把被 1.0 改名成 `-old` 的原有页面（首页、关于、常见问题、批发）改回原网址，并恢复原来的网站首页，本脚本建的同名页面改成草稿 `aurora-*` → 标准目录里和原有产品同型号的那部分改成草稿 → 在桌面导出只读诊断包 `aurora-audit-修复后.zip`。都不删除任何内容，后台随时可以恢复。

## 产品实拍图（先清点核对，确认后再上传）

分三步，第 1 步不改网站、也不改原图：

```bash
# 第 1 步：清点（只读）。运行后把照片文件夹拖进终端窗口
cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/claude/minimax-model-setup-dfLij.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx' bash kinglogan-claude-minimax-model-setup-dfLij/aurora-cigars/scripts/run_photos.sh
# 第 2 步：Claude 核对后提交 content/photo-mapping.csv，你确认后上传（同一条命令，末尾加 apply）
… run_photos.sh apply
# 一次做完（先全部导入、之后再核对）：清点备份 → 修正名称 → 合并同名重复 → 重复型号改草稿 → 限量款建草稿 → 拿不准的名称标红 → 按对照表配图上传
… run_photos.sh auto
# 删除上一次被转歪、已经没有产品在用的旧实拍图（只删按产品 SKU 命名、带 -rotated 的图，删除后不能恢复）
… run_photos.sh cleanup
# 撤销：按桌面上的备份恢复产品名称、图片和上架状态（用「清点时」的备份可以撤销 auto 的全部改动）
… run_photos.sh restore ~/Desktop/aurora-产品图片备份-清点时-日期.json
```

- **一次做完**（`auto`）：上传按 `content/photo-mapping.csv`（逐张看图核对过的对照表）里「确认」的照片，「待确认」「不上传」的不动。
  不再按文件名自动配图：中文文件名逐字比对会把「世纪一」配成「半世纪」、「鉴赏家2号」配成「2号」。
  每一步都可以重复运行：名称已改好、已合并、已标红、已按同样照片配好的产品都会跳过；一款上传失败不影响其他款，重跑只补失败的
- **站上没有的限量 / 特别版新建为草稿**（`create-drafts`，表在 `content/new-products.csv`）：照片里有、网站上没有的产品
  （目前 59 款：潘趣各地区限量、乌普曼全球限量、特立尼达保湿盒等）建成草稿，SKU 为 `LTD-001` 起；
  名称用照片文件名原文（文件名没写品牌的，按环标在前面加上品牌），分类为 Collection + 品牌 + Limited Editions，
  价格、规格、库存留空，不对外显示。同时列进 `name-review.csv` 标红，补好英文官方名和资料后再发布。
  已有同一 SKU 或同名产品的不新建
- **照片方向**：上传的样子就是核对时看到的样子（按像素原样）。这批照片的 EXIF 里都带着「旋转 90°」的方向标记，
  而像素本身是正的，WordPress 会照着标记把图转歪（文件名带 `-rotated`），所以上传前在副本上去掉 EXIF（同时去掉拍摄地点等信息）。
  处理方式有变化时 `PHOTO_PREP` 加 1，重新运行会把之前按旧方式上传的照片重传一遍
- **单支雪茄的横条图**（长宽比超过 2，例如 900×130）：上传前在副本上转成 JPG，放到白底正方形画布正中（两端各留约 6%），
  因为商品卡、产品页都是正方形框、WooCommerce 缩略图也按正方形裁切，直接上传只会显示中间一截。整盒照片等普通照片原样上传
- **名称修正**（`rename`，表在 `content/name-fixes.csv`）：只改当前名称仍等于表里原值的产品，已经被人改过的不动；产品网址不变。
  目前 63 项：拼写错误（Siglo Ill、Connossieur、Upmann Upmann）、官方型号写法（Edmundo、Royal Coronas、Maduro 5 Genios 等）、
  品牌写法统一（H. Upmann、Partagás、Bolívar、Ramón Allones 等）、名字里夹着的换行、标准目录里重复的「Punch Punch Punch」，
  以及照片环标能证实的官方名（Montecristo Slam → Open Slam）。
  很长的地区限量名只去掉换行，文字不改
- **合并同名重复**（`merge`）：站点原有产品里完全同名的（例如两个 Cohiba Siglo VI），保留资料最全的一款（同样全时保留编号小的），
  另一款有、保留款缺的资料补过来，另一款改为草稿并记下 `aurora_merged_into`。不删除产品
- **拿不准的官方名称标红**（`mark-review`，表在 `content/name-review.csv`）：写入 `aurora_review`，插件把这些产品在商品卡和产品页上的名称标红并注明「名称待核对」，
  后台产品列表也标出。只在内部预览模式下或管理员登录时显示。核对完把那一行从表里删掉再运行一次即可取消

- **清点**（`photo-inventory`）：扫描文件夹及子文件夹，记录每张图的路径、大小、尺寸、SHA1 指纹（找出内容完全相同的重复文件），
  生成长边 1000px 的缩略图副本，附上网站现有产品清单和按文件名的初步建议，打包成桌面上的「aurora-图片清单.zip」；
  同时把所有产品现有的图片备份成 JSON
- **对照表**（`content/photo-mapping.csv`）：`file`（相对路径）、`sha1`（核对时这张照片的指纹）、`sku`、`product`、
  `role`（主图 / 包装 / 本体 / 细节 / 其他）、`order`、`status`（确认 / 待确认 / 不上传）、`note`。只有「确认」的行会上传。
  拖进多个文件夹、不同文件夹里有同名照片时（例如「1211」和「热门 2」），按指纹上传核对过的那一张；内容对不上的不上传
- **上传**（`photo-apply`）：先列出计划，输入 `y` 才执行；先备份涉及的产品现有图片；同一产品按 主图 → 包装 → 本体 → 细节 → 其他 排列，
  第一张是产品主图，其余进 WooCommerce 产品图库；上传的是副本（Mac 上 HEIC 转 JPG、大图缩到长边 2000px），文件按 SKU 命名，原图不动；
  完成后自动导出诊断包，诊断包会逐张试加载实拍图（`image_check`）
- **按文件名的初步建议**：SKU、英文名、中文名都能对，不分大小写、重音、空格和下划线，子文件夹名也参与；数字和罗马数字必须一致；
  上架的产品优先；两款同样接近时标为不确定。建议只是参考，对照表以人工核对为准

## 上线步骤

1. **生成新的 Application Password**：WP 后台 → 用户 → 个人资料 → 拉到底部的 Application Passwords。旧的那个请删掉。同时记下页面顶部的「用户名」（不是显示名称）
2. **安装插件**：插件 → 安装插件 → 上传插件，选择 `dist/aurora-core.zip`，然后启用
3. **在 Mac 终端运行**：

```bash
cd aurora-cigars/scripts
export AURORA_USER='后台登录用户名'
export AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'

python3 aurora_setup.py check                                   # 测试连接
python3 aurora_setup.py configure                               # 设置 USD、迪拜，关闭配送
python3 aurora_setup.py import ../content/catalog.csv            # 先上 80 款标准型号（可选）
python3 aurora_setup.py import ~/路径/aurora_products_full.csv --dry-run   # 先看字段映射对不对
python3 aurora_setup.py import ~/路径/aurora_products_full.csv             # 正式导入（按 SKU 去重，可以重复跑）
python3 aurora_setup.py pages                                   # 创建 6 个页面，并设首页
python3 aurora_setup.py images                                  # 给没图的产品配品牌图 + 品牌分类封面
python3 aurora_setup.py images --photos ~/实拍图                 # 以后有实拍图：按 SKU 命名（COH-ROB-25.jpg，图集 COH-ROB-25-2.jpg）
python3 aurora_setup.py images --urls temp_images.csv            # 内部预览用的临时网图（两列：sku,url）
python3 aurora_setup.py images --clear-temp                      # 上线前把临时网图全部换回品牌图
python3 aurora_setup.py menu                                    # 创建主导航
python3 aurora_setup.py cleanup                                 # 停用 YITH、Click to Chat、PayPal，删除遗留安装片段
python3 aurora_setup.py restore-pages                           # 把 -old 页面改回原网址，恢复原首页
python3 aurora_setup.py dedupe --dry-run                        # 列出标准目录里与原有产品重复的型号；去掉 --dry-run 改为草稿
python3 aurora_setup.py audit                                   # 只读诊断包（主题、插件、片段、页面 HTML 和 CSS），默认存到桌面
```

`pages` 默认不碰站点原有的同名页面；确实要替换时加 `--replace-pages`（原页面改名为 `-old`，内容备份到 `content/backup/`）。`import` 更新已有产品时不改它的发布状态，所以 dedupe 改成草稿的重复款不会被重新发布。

品牌分类会自动对上 `brands.json` 里的介绍。CSV 里的品牌写「Cohiba」「高希霸」或「cohiba」都可以，有没有重音（Partagás / Partagas）也都能识别。

如果 CSV 的列名没有被自动识别，用 `--map` 手动指定，例如：`--map price=零售价USD --map name_cn=产品中文名`。运行 `--dry-run` 时会列出所有可用字段。

4. **停用不再需要的插件**：运行 `cleanup` 即可，这些插件随时可以在后台重新启用

## 图片来源规则

每款产品都记录了图片来源 `aurora_image_source`，优先级是：实拍图（photo）> 临时网图（temp）> 品牌渲染图（brand）。临时网图只能在内部预览模式下用；正式上线前，要么换成实拍图或供应商授权图，要么运行 `--clear-temp` 换回品牌图。

## 还没做的

- 多语言（English / عربي）：需要先选定翻译插件（Polylang 或 TranslatePress）
- n8n 自动化：把询价记录到表格或 CRM
- 实拍产品图：已向 New Leaf（Amin）起草邮件索要官方产品图（Gmail 草稿）。拿到后放进一个文件夹，按 SKU 命名，跑 `images --photos` 即可替换。不能用零售商网站上的照片

## 产品 CSV 能识别的列

中英文列名都可以，大小写和空格都不影响：

SKU / 编号 · 中文名 · English Name · 品牌 · 价格（可以写成 "USD 1,280"）· 每盒支数 · 型号 · 长度 · 环径 · 浓度 · 茄衣 · 产地 · 限量（是 / yes）· 防伪 · 库存（数字，或「现货 / 缺货」）· 图片（URL，多张用 `|` 分隔）· 品鉴描述 · 简介 · 分类

## 测试

```bash
php tests/build_preview.php > /tmp/preview.html     # 整站静态预览（示例产品）
php tests/render_harness.php > /tmp/normal.html && php tests/render_harness.php limited > /tmp/limited.html
node tests/browser_test.js /tmp/normal.html /tmp/limited.html /tmp      # 需要 playwright
php tests/integrate_mode_test.php                                         # 整合模式（站点有自己的店面片段时）
php tests/private_mode_test.php anon                                      # 内部预览模式：anon / loggedin / key-good / key-bad / off
node tests/integrate_bridge_test.js <诊断包目录> <vendor 目录>            # 用线上页面测「＋」和「加入询价清单」
node tests/render_audit.js <诊断包目录> <vendor 目录> <输出目录> [CSS]      # 离线还原线上页面截图（AURORA_ONLY=home,shop 只渲染部分页面；AURORA_LOCAL_PLUGIN=1 用本地插件文件看即将部署的效果）
python3 tests/photo_match_test.py                                       # 照片按文件名的初步建议、重复型号判定
python3 tests/mock_wc_server.py 8765 &                                   # 模拟 WooCommerce API（MOCK_BLOCK_DELETE=1 模拟拦截 DELETE）
AURORA_SITE=http://127.0.0.1:8765 AURORA_USER=tester AURORA_APP_PASSWORD='abcd efgh ijkl' \
  python3 scripts/aurora_setup.py all tests/sample_products.csv
```

## 设计相关的 Claude skill

仓库根目录 `.claude/skills/` 里有四个 skill，在这个仓库里用 Claude Code 时会自动加载：

| skill | 什么时候用 |
|---|---|
| `aurora-design-system` | 视觉规范：配色变量、字体、直角细线、商品卡和产品页组件、图片呈现、中英文命名 |
| `aurora-design-review` | 设计审查：拿诊断包离线还原电脑/手机页面，`AURORA_PROBE=1` 测字号、对比度、点按区、溢出，按 P0/P1/P2 出清单 |
| `aurora-ui-change` | 动手改界面：改哪里（插件整合样式 / 用户片段 / 页面内容）、样式覆盖顺序、版本号、测试、`run_site.sh update` 上线、回滚 |
| `aurora-product-photos` | 产品照片：清点、看图核对（对照图、长宽比辨认型号）、每批一份对照表、新款建草稿、上传、验收、对照审查页 |
