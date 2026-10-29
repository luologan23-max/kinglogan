---
name: aurora-ui-change
description: 动手修改 Aurora Cigars 网站（WordPress + WooCommerce + Astra + Code Snippets + 自研 aurora-core 插件）的外观或前台功能时的落地流程：判断改哪里、怎么改、怎么本地预览和测试、怎么让用户在 Mac 上一条命令上线、出问题怎么回滚。只要要改这个网站的 CSS、页面、商品卡、产品页、导航、按钮、文案位置、手机布局，或者用户说「把这个改一下」「按审查结果优化」「字太小了调大」「上线这个改动」，就按这个流程走。Use whenever implementing or shipping any front-end change to the Aurora Cigars site.
---

# 改 Aurora 网站界面的流程

视觉标准见 `aurora-design-system`，找问题见 `aurora-design-review`。这里讲的是**怎么把改动安全地做到线上**。

## 先记住三个限制

1. **云端连不上网站**。所有写入网站的操作都由用户在自己 Mac 的终端里运行脚本完成；我们改的是 GitHub 仓库
   `luologan23-max/kinglogan`（工作分支见 `git branch --show-current`），用户的命令从这个分支下载最新代码。
2. **店面外观主要是用户自己的代码片段**（后台 Code Snippets），不是主题、也不是插件。插件处于「整合模式」：只补漏、不接管。
3. **网站处于内部预览模式**：访客看到「即将上线」，用户和预览链接（`?aurora_preview=密钥`）能看到真站。

## 1. 判断改在哪里

| 想改的 | 改哪里 | 为什么 |
|---|---|---|
| 现有组件的颜色、字号、间距、对比度、点按区、手机适配 | 插件 `plugin/aurora-core/assets/aurora-integrate.css` | 有版本、能测试、一条命令上线、可回滚；不碰用户片段 |
| 修前台脚本问题（按钮没反应、清单不同步） | 插件 `aurora-integrate.js` | 同上 |
| 手写页面（首页、关于、FAQ、批发、限量等）的版式 | 插件 `aurora-pages.css`；内容本身在 WordPress 页面里 | 页面是手写 HTML，插件识别后给它加这份样式 |
| 页面文字、板块增删 | WordPress 页面内容（先备份原内容，`aurora_setup.py` 的 pages / restore-pages 有现成逻辑） | 内容改动要用户确认 |
| 产品页、商品卡的 HTML 结构 | 用户的片段 #14（产品页）/ #11（卡片样式）/ #15（导航页脚）| 结构只能在片段里改；先把改法讲清楚、征得同意，改前导出原代码备份 |
| 产品名称、图片、上下架 | 产品数据，用 `scripts/aurora_setup.py` 的 rename / photo-* / create-drafts 等命令 | 见 `aurora-product-photos` |
| 新功能（全站开关、短代码、跳转） | 插件 `aurora-core.php` | |
| 换 WhatsApp 号码 | `run_site.sh whatsapp '+971 5X XXX XXXX'` | 号码写死在片段 #13/#14/#15、页面正文和插件设置里，这条命令一次全换（先备份）；号码先和用户逐位核对 |

不要做：在 Elementor 或主题定制器里改（这些页面不用它们，改了会出现两套样式）；加购物车 / 结账；删除用户的片段或页面
（停用、改草稿可以，删除要用户明确同意）。

### 样式覆盖要注意顺序

页面 `<head>` 里的顺序是：片段 #14/#15 的 `aurora-bom-css` → 主题和 WooCommerce → 插件 `aurora-base` / `aurora-integrate` →
**片段 #11 的 `aurora-site-css-1`（最后）**。所以插件里写的规则要压过 #11，必须选择器更具体（例如 `li.product .aur-card .aur-card-name`、
`body.single-product .aur-btn-wa`），实在不行再用 `!important`；压 `aurora-bom-css` 则同等具体度就够。
改之前在诊断包的样式表里搜一下目标选择器，看现在是哪条规则在生效。

整合样式只在整合模式下加载；触屏相关的规则写在 `@media (hover: none)` 里（插件里已有这一段，沿用）。

## 2. 改动 + 版本号

1. 改 `plugin/aurora-core/` 下的文件，规则旁边用一行中文注释写清楚「为什么」（和现有代码一致）。
2. **每次要上线都把版本号加一**：`aurora-core.php` 顶部的 `Version:` 和 `define( 'AURORA_CORE_VERSION', ... )` 两处一起改。
   安装脚本发现网站上已经是同一版本会直接跳过，不加版本号等于没上线；版本号也用于让浏览器重新加载样式。
3. 打包：`bash scripts/build_zip.sh`（生成 `dist/aurora-core.zip`，这个文件要一起提交——用户的命令装的就是它）。

## 3. 本地验证（都在云端跑，不碰网站）

需要一份最新的诊断包（没有就请用户运行 `run_site.sh audit`，见 `aurora-design-review`）。

```bash
cd aurora-cigars
php tests/integrate_mode_test.php                                  # 整合模式、手写页面、跳转、标红
node tests/integrate_bridge_test.js <诊断包目录> <vendor目录>        # 用线上真实页面测询价清单、按钮、规格表
python3 tests/photo_match_test.py && python3 tests/photo_apply_test.py
# 改前改后对比截图（AURORA_LOCAL_PLUGIN=1 = 用本地插件文件；AURORA_PROBE=1 = 同时测字号/对比度/点按区）
AURORA_ONLY=shop,product_existing node tests/render_audit.js <诊断包目录> <vendor目录> <before目录>
AURORA_LOCAL_PLUGIN=1 AURORA_PROBE=1 AURORA_ONLY=shop,product_existing node tests/render_audit.js <诊断包目录> <vendor目录> <after目录>
```

- vendor 目录用 `bash tests/fetch_vendor.sh <目录>` 准备一次。
- 截图看改动的区域（裁剪后并排），电脑和手机都要看；probe 的数字应该朝预期方向变化，不能引入横向溢出。
- 离线截图里实拍图是空白的，这是正常的（拿不到网站图片）。

## 4. 提交并让用户上线

1. 提交前检查暂存的改动里没有密码之类的敏感信息（应用密码、数据库密码都不能进仓库），然后提交并推送到工作分支。
2. 给用户一条命令（中文说明在前，命令单独放代码块，应用密码让用户自己填）：
   ```
   cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/<分支>.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='应用密码' bash kinglogan-<分支名里的 / 换成 ->/aurora-cigars/scripts/run_site.sh update
   ```
   它会检查连接 → 安装新版插件（借 Code Snippets 建一个临时安装片段，装完自动删除，删不掉就停用）→ 导出 `aurora-audit-更新后.zip`。
3. 用户发回诊断包后：确认 `report.json` 里插件版本是新的、页面都能打开、probe 指标改善，再用截图向用户说明改了什么。
4. 安装失败（例如 Code Snippets 接口报错）时，退路是让用户在后台「插件 → 安装插件 → 上传插件」手动上传 `dist/aurora-core.zip`。

## 5. 回滚

- 插件：回退提交（`git revert`），版本号继续往上加（不能比线上低，否则会被跳过），重新打包推送，用户再运行 `run_site.sh update`。
- 产品数据：桌面上的 `aurora-产品图片备份-*.json` 可以用 `run_photos.sh restore <备份>` 恢复名称、图片、上下架状态。
- 页面内容：`aurora_setup.py restore-pages` 能把改过的原有页面换回来。

## 和用户沟通

用户是中文母语的店主，用终端但不写代码。说明改动时讲「看起来会有什么不同」，配前后截图；需要用户运行的东西一次只给一条命令，
写清楚要拖什么、要等多久、跑完把哪个文件发回来。改结构、删内容、换风格之前先问。
