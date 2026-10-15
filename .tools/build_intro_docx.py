# -*- coding: utf-8 -*-
"""生成《30秒团队自我介绍》Word 文档。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
MONO_FONT = "Consolas"

doc = Document()

# ---------- 全局样式 ----------
normal = doc.styles["Normal"]
normal.font.name = BODY_FONT
normal.font.size = Pt(10.5)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.25

for name, size in (("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11.5)):
    st = doc.styles[name]
    st.font.name = HEAD_FONT
    st.font.size = Pt(size)
    st.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    st._element.rPr.rFonts.set(qn("w:eastAsia"), HEAD_FONT)

# 页面：A4 + 较窄页边距
for section in doc.sections:
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)

CONTENT_WIDTH = Cm(21.0 - 4.4)


def set_run(run, bold=None, size=None, font=None, color=None, italic=None):
    if font:
        run.font.name = font
        run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color:
        run.font.color.rgb = color
    return run


def para(text="", style=None, bold=False, size=10.5, align=None, space_after=4,
         font=BODY_FONT, color=None, indent=None):
    p = doc.add_paragraph(style=style)
    if text:
        set_run(p.add_run(text), bold=bold, size=size, font=font, color=color)
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if indent is not None:
        p.paragraph_format.left_indent = Cm(indent)
    return p


def force_fixed_layout(t, total_cm, widths):
    """锁定固定布局、总宽，并让 tblGrid 与单元格宽度一致（否则渲染器按网格撑宽表格）。"""
    from docx.oxml import OxmlElement
    tblPr = t._tbl.tblPr
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(int(round(total_cm * 567))))
    grid = t._tbl.find(qn("w:tblGrid"))
    if grid is not None:
        for col, w in zip(grid.findall(qn("w:gridCol")), widths):
            col.set(qn("w:w"), str(int(round(w.cm * 567))))


def shade(cell, hexcolor):
    from docx.oxml import OxmlElement
    tcPr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:color"), "auto")
    el.set(qn("w:fill"), hexcolor)
    tcPr.append(el)


def add_table(rows, widths=None, header=True, font_size=9.5, first_col_bold=False):
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, val in enumerate(row):
            cell = cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.1
            set_run(p.add_run(str(val)),
                    bold=(header and i == 0) or (first_col_bold and j == 0),
                    size=font_size, font=BODY_FONT)
            if header and i == 0:
                shade(cell, "DCE6F1")
    if widths:
        total = sum(w.cm for w in widths)
        for r in t.rows:
            for j, w in enumerate(widths):
                r.cells[j].width = w
        force_fixed_layout(t, total, widths)
    return t


# ---------- 标题 ----------
para("脑控游戏 · 运动想象在线解码模块", style="Heading 1", align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=2)
para("团队自我介绍（30 秒版）", style="Heading 2", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

add_table([
    ["使用场合", "与天津大学脑机方向老师的技术交流会 · 开场自我介绍"],
    ["团队", "智能医学工程专业大一学生团队（4 人）：蓝喜阳（组长）、阎浩文、黄凯森、王释贤"],
    ["时长", "主体 30 秒（约 140 字，正常语速）；附备用加长版与精简版"],
    ["合作企业", "翔宇医疗｜项目周期 10 周（10/13 – 12/15）"],
], widths=[Cm(2.8), Cm(13.8)], header=False, first_col_bold=True)
doc.add_paragraph()

# ---------- 一、正文 ----------
para("一、30 秒主体稿（照读即可）", style="Heading 2")
para(
    "老师好！我们是智能医学工程的大一团队，四个人，今天来请教方向。"
    "我们给翔宇医疗做“运动想象”在线解码：想象动左手或右手，就能控制小游戏。"
    "我们只学过一点 Python，基础比较弱，但愿意继续学。"
    "最担心三件事：脑电很弱，眨眼、晃一下就受干扰；设备型号和通道顺序还没确认；"
    "离第一版只有两周。我们希望准确率不低于 50%，正式评测争取 Kappa 大于 0.3，"
    "换设备换电脑都能跑。请老师看看我们哪里想错了、哪些坑能提前避开。谢谢老师！",
    size=11, space_after=6,
)
para("（以上 167 个汉字。掐在 30 秒内需稍快（约 330 字/分钟），建议先掐表读两遍；"
     "若读下来超时，删掉“换设备换电脑都能跑”与“但愿意继续学”两句。）",
     size=9, color=RGBColor(0x59, 0x59, 0x59), space_after=8)

para("二、逐句拆解与时间分配", style="Heading 2")
add_table([
    ["段落", "内容要点", "话术（可直接用）", "用时"],
    ["① 身份", "专业、年级、人数、来意", "我们是智能医学工程的大一团队，四个人，今天来请教方向。", "4 s"],
    ["② 在做什么", "一句话说清项目", "给翔宇医疗做“运动想象”在线解码——想象动左手或右手，就能控制小游戏。", "7 s"],
    ["③ 现状", "大一、基础弱、已学什么、肯不肯学", "我们只学过一点 Python，基础比较弱，但愿意继续学。", "3 s"],
    ["④ 技术痛点", "三条最真实的风险", "脑电很弱，眨眼、晃一下就受干扰；设备型号和通道顺序还没确认；离第一版只有两周。", "6 s"],
    ["⑤ 期望效果", "准确性 + 兼容性", "希望做到准确率不低于 50%，正式评测争取 Kappa 大于 0.3，换设备、换电脑都能跑。", "7 s"],
    ["⑥ 请求", "明确我们要什么", "请老师帮我们看看，哪里想错了、哪些坑能提前避开。", "3 s"],
    ["合计", "—", "—", "≈ 30 s"],
], widths=[Cm(1.9), Cm(3.4), Cm(9.0), Cm(2.2)])

doc.add_paragraph()
para("三、备用版本", style="Heading 2")

para("A. 精简版（15 秒，时间被压缩时用）", style="Heading 3", bold=True)
para(
    "老师好，我们是智能医学工程大一团队，四人在做翔宇医疗的“运动想象”在线解码模块——"
    "想象动左右手就能控制游戏。我们只初步学过 Python，基础比较弱。"
    "主要困难是脑电信号弱、干扰多，设备通道顺序还没确认，时间又紧。"
    "我们的目标是把解码做出来，准确率不低于 50% 作底线，兼容性尽量好，今天想请老师指指方向。谢谢！",
    size=10.5, space_after=6,
)
para("（约 155 字，正常语速约 35 秒；若严格限 15 秒，只保留①②④⑥四句。）",
     size=9, color=RGBColor(0x59, 0x59, 0x59), space_after=8)

para("B. 加长版（约 60 秒，只在需要展开时用；正式开场仍用上面的 30 秒稿）", style="Heading 3", bold=True)
para(
    "老师好，我们是智能医学工程专业的大一学生团队，四个人：我负责统筹和算法，"
    "一位同学主攻算法，一位做数据评测和游戏，一位负责工程与通信接口。"
    "项目是给翔宇医疗做“运动想象”的在线解码模块：用户想象动左手或右手，"
    "模块判断出“左 / 右 / 不动”，再通过 WebSocket 把结果送给一个小游戏。"
    "我们团队都是大一，基础相对比较弱，目前只初步学过 Python、有一点数理基础，"
    "但每天都在学，愿意为这个项目补齐信号处理和机器学习的基础。",
    size=10.5, space_after=4,
)
para(
    "我们预计会遇到三方面痛点。第一是信号本身：脑电非常微弱，眨眼、咬牙、身体晃动都会污染它，"
    "而我们要判断的“想象动作”只体现在很窄的频段上，信噪比很低，容易误判；"
    "同时不同人差别很大，还有一部分人天生对运动想象不敏感。"
    "第二是设备和工程：采集设备的型号、通道数和通道顺序还没拿到书面确认，"
    "顺序一旦弄错，左右会稳定地判断反；而且我们要做的是“边收边算”，"
    "不能用未来的数据，理论上比离线做实验容易掉精度。"
    "第三是团队和时间：算法、工程、游戏三条线要并行推进，"
    "我们既要补基础，又只有两周时间就要交出第一个可运行版本。",
    size=10.5, space_after=4,
)
para(
    "我们希望达到的效果有三点：一是真的具备运动想象解码能力，"
    "能把“想象左手 / 想象右手 / 不动”分出来，准确率不低于 50% 作为底线，"
    "正式评测争取 Kappa 大于 0.3；二是兼容性比较好，尽量不绑定某一台设备或某一种电脑，"
    "换数据源、换机器都能跑；三是整个流程能现场演示，让老师或企业按文档就能启动。"
    "今天最想请教的是：我们这条技术路线有没有明显想错的地方，以及未来一年该先验证什么。谢谢老师！",
    size=10.5, space_after=8,
)

# ---------- 四、口径说明 ----------
para("四、两个数字的口径说明（被追问时怎么讲）", style="Heading 2")
add_table([
    ["数字", "怎么解释（避免显得不懂）"],
    ["准确率\n不低于 50%",
     "先主动说明：二分类随机猜就是 50%，所以 50% 是“必须超过”的底线，不是成绩。"
     "我们的意思是：第一阶段先证明闭环真的能跑通、能超过瞎猜；"
     "在此基础上按标准口径评测，正式目标是 Kappa 大于 0.3。"],
    ["Kappa > 0.3",
     "Kappa 是扣掉“瞎猜也能蒙对”之后的真实水平。0.3 是及格线，0.6 以上算好——"
     "这是我们课程项目的验收线，属于合理但不夸张的目标。"],
    ["兼容性比较好",
     "具体指三件事：不依赖显卡（普通笔记本能跑）；换数据源（模拟 / 回放 / 真实设备）不用改主流程；"
     "输出用 WebSocket + JSON，游戏、轮椅等外部程序都能订阅。"],
], widths=[Cm(3.0), Cm(13.6)])

doc.add_paragraph()

# ---------- 五、可能被追问 ----------
para("五、可能被追问的问题与简短应答", style="Heading 2")
add_table([
    ["老师可能问", "我们怎么答（一句话）"],
    ["你们为什么要做运动想象，不做更快的？",
     "康复场景里患者不需要盯屏幕、不需要外部刺激，运动想象最贴合翔宇医疗的场景；慢是这个范式的固有代价，我们接受。"],
    ["50% 的目标是不是太低了？",
     "50% 是我们的底线而不是目标；正式评测按 Kappa 大于 0.3 要求，并且我们拿到真实数字之前不对外报准确率。"],
    ["打算用深度学习吗？",
     "本期不用。单被试数据只有几百个 trial，容易过拟合，跨被试常打不过传统方法；而且延迟瓶颈在“等够 2 秒数据”，换模型对速度几乎没帮助。"],
    ["两周能做完吗？",
     "已定“先降功能、不降节点”：保留解码链路 + 游戏 + 通信闭环，其余延后；每周例会重新判断是否降级。"],
    ["零基础怎么补？",
     "按“够用就行”的顺序学：先跑通链路、再看懂滤波和特征、最后补分类器原理；四人分工各管一块并互相讲一遍。"],
], widths=[Cm(4.6), Cm(12.0)])

doc.add_paragraph()

# ---------- 六、注意 ----------
para("六、讲的时候不要说的三句话", style="Heading 2")
for txt in (
    "① 不说“我们什么都不会”——改成“我们基础比较弱，但已经初步掌握 Python，愿意继续学”；",
    "② 不说“准确率肯定能到 90%”——我们没有任何实测依据，说了就是给自己挖坑；",
    "③ 不说“老师能不能帮我们写代码”——我们要的是判断和方向，代码自己写。",
):
    para(txt, size=10.5, space_after=3, indent=0.4)

doc.add_paragraph()
para(
    "注：本文中“准确率 50%”“Kappa > 0.3”“兼容性好”等表述为团队对第一阶段目标的设定，"
    "不构成已实现的性能指标；真实准确率将在中期评审用公开数据集（BCI IV 2a）按标准口径给出，"
    "在此之前不对外报告任何准确率。",
    size=9, color=RGBColor(0x59, 0x59, 0x59),
)

out = r"D:\校企合作项目\团队自我介绍_30秒.docx"
doc.save(out)
print("saved:", out)
