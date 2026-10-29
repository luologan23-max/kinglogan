---
name: aurora-design-review
description: 审查 Aurora Cigars 网站（迪拜古巴雪茄询价站）的设计和体验，给出有截图、有数据、按优先级排好的改进清单。用户说「看看网站哪里不好」「帮我优化网站」「提提意见」「手机上体验怎么样」「询价的人少」「对比一下别的雪茄网站」「上线前检查一遍」，或者发来诊断包（aurora-audit*.zip）想知道效果时，都用这个流程，不要只凭印象给泛泛的建议。Use for any design/UX review, critique or audit of the Aurora Cigars website.
---

# Aurora 网站设计审查

目标：让用户拿到一份能直接动手的清单——每条都有证据（截图或测量值）、影响、具体改法和改在哪里，按轻重排好。
视觉标准以 `aurora-design-system` 为准；要动手改时转到 `aurora-ui-change`。

## 1. 拿到证据

这台云端电脑连不上网站（Cloudways 拒绝连接），所以一切从**诊断包**开始：

- 用户发来的 `aurora-audit*.zip` 里有：各页面 HTML（首页、商店、分类、两个产品页、所有已发布页面）、全部样式表、
  产品清单（名称、状态、分类、图片地址、内部标记）、实拍图可访问性检查、插件和代码片段列表。
- 先看压缩包里每个文件的时间（`zipfile` 的 `date_time`）和 `report.json` 里的插件版本，确认是最新的——用户发错过旧包。
- 没有诊断包就请用户在 Mac 终端运行（只读，不改网站），然后把桌面上的 `aurora-audit.zip` 发过来：
  ```
  cd ~/Downloads && curl -sL -o aurora.zip https://github.com/luologan23-max/kinglogan/archive/refs/heads/claude/minimax-model-setup-dfLij.zip && unzip -qo aurora.zip && AURORA_APP_PASSWORD='应用密码' bash kinglogan-claude-minimax-model-setup-dfLij/aurora-cigars/scripts/run_site.sh audit
  ```
  （分支名以仓库当前分支为准；应用密码用户自己有，不要写进仓库。）
- 补充数据：WordPress.com 连接器（`wpcom-mcp-content-authoring`，站点 `wordpress-1627597-6431471.cloudwaysapps.com`）能读 Jetpack 同步的产品、页面、媒体列表，可以核对数量和最近改动；它的写操作走不通。

## 2. 离线还原并测量

```bash
cd aurora-cigars
mkdir -p <scratch>/audit && unzip -qo <诊断包> -d <scratch>/audit
bash tests/fetch_vendor.sh <scratch>/vendor            # jQuery 等前端库，第一次需要
AURORA_PROBE=1 AURORA_ONLY=home,shop,category,product_existing \
  node tests/render_audit.js <scratch>/audit <scratch>/vendor <scratch>/render
```

- 每页出电脑（1440 宽）和手机（390 宽，按触屏模拟）两张整页截图，`AURORA_PROBE=1` 时每张截图旁边还有一个同名 `.json`：
  横向溢出像素、过小的字（中文 < 12px、其他 < 10px）、手机上过小的点按区（< 40px）、对比度不达标（WCAG：小字 < 4.5、大字 < 3），
  每类有数量和前 12 个例子（元素、字号、颜色、文字）。
- `AURORA_ONLY` 的页面名就是诊断包 `html/` 里的文件名（`page_about`、`page_limited-editions`……），不写就全渲染。
- 要预览本地还没上线的插件样式：加 `AURORA_LOCAL_PLUGIN=1`。
- **截图里的产品实拍图是空白的**（离线拿不到网站图片，只有品牌渲染图能显示），所以不要据此说「图片没显示」。
  图片本身的问题看诊断包的 `image_check`、产品的 `image_srcs`（文件名带 `-rotated` 说明被 WordPress 转歪过），
  以及照片清点包和对照审查页（见 `aurora-product-photos`）。
- 截图很长，看之前用 Pillow 裁成首屏、关键区块（商品卡网格、产品页首屏、手机底部操作条）再看，必要时并排拼图对比。

## 3. 逐项检查

清单在 `references/checklist.md`，按「信任感 → 找货 → 商品卡 → 产品页 → 询价转化 → 手机 → 一致性 → 内容完整度 → 可读性 → 性能」分组，
每项写了怎么查。几条这个站特有、最容易漏的：

- 转化只有 WhatsApp 一条路：每个产品页、商品卡、手机底部都要能一步发起询价，WhatsApp 预填内容要带产品名（中英文）和数量。
- 21+ 年龄验证、持牌信息、Habanos 官方渠道 / 防伪查验是信任基础，不能被视觉调整弱化。
- 草稿和标红：前台不该出现「名称待核对」红字（只有管理员和预览模式可见）；限量版页面空着时要有像样的空状态。
- 实拍图和品牌渲染图混排、两套 `:root` 变量、9px 中文、低对比度辅助色——这些是已知问题，复查时确认改了没有。

## 4. 输出格式

先给一句话总评，再按优先级列问题。每条用这个结构：

```
### [P0/P1/P2] 问题标题（一句话）
- 证据：截图（裁好的）或测量值，写明页面、电脑/手机、选择器
- 影响：对哪类客户、哪一步造成什么后果
- 建议：具体改法（数值、文案、布局），必要时给前后对比图
- 改在哪：片段 #11/#14/#15 / 插件 aurora-integrate.css / 页面内容 / 产品数据；工作量 小/中/大
```

- P0：影响信任、合规或询价转化（按钮点不到、WhatsApp 发不出、年龄验证失效、页面报错）。
- P1：明显影响观感或易用（手机上字太小、图片风格混乱、关键文字对比度不够）。
- P2：打磨项。
- 用户是中文母语的店主，不是开发者：结论和建议用平实的中文，术语第一次出现时顺手解释；选择器、文件名放在「改在哪」里给后续动手用。
- 条目多、有截图时，把报告做成 Artifact 页面（先 `Artifact` quickstart，截图压缩后内嵌），聊天里只给结论和链接；
  只有三五条时直接在聊天里写。
- 最后列「需要你决定的事」（改风格方向、删内容、要不要上线某个改动），不要替用户做这些决定。

## 5. 不要做的事

- 不要只凭截图审美下结论；能量的（字号、对比度、点按区、溢出、图片尺寸）都用 probe 的数据说话。
- 不要建议换主题、换 Elementor 重做、加购物车——这个站的架构是刻意的（见 `aurora-ui-change`）。
- 不要改网站：审查只读。改动走 `aurora-ui-change` 的流程，由用户在 Mac 上执行。
