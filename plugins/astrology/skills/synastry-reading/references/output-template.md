# Adaptive output template

Use the selected language's universal headings exactly and in order. Replace every angle-bracketed slot in the draft. Insert only explicitly authorized canonical modules.

## Contents

1. [English universal report](#english-universal-report)
2. [English conditional modules](#english-conditional-modules)
3. [Chinese universal report](#chinese-universal-report)
4. [Chinese conditional modules](#chinese-conditional-modules)
5. [Evidence-limit form](#evidence-limit-form)

## English universal report

```markdown
# Synastry Reading: <validated display labels or subject IDs>

## Basis, provenance, and limitations

- Source: validated synastry JSON v2, chart ID <chart-id>
- Calculation and aspect profiles: calculation <configuration.calculation_profile>; aspects <configuration.aspect_profile>.
- House system and configured orbs: <configuration.house_system or "not configured">; major <configuration.major_orb>°; minor <configuration.minor_orb>°.
- Backend provenance: requested <provenance.requested_backend>; actual <provenance.actual_backend>; software <provenance.software_version>; binding <provenance.binding_version>; timezone <provenance.timezone_source>; return flags <comma-separated provenance.return_flags or "none">; warnings <pipe-separated provenance.warnings or "none">.
- Explicit relationship context: Not stated
- Data limitations: <copy one exact limitation.message per line, or "None recorded">

## Repeated interaction patterns

<Conditional synthesis with inline evidence ID(s).>

## Reciprocity and asymmetry

<Conditional comparison preserving subject ownership and direction with inline evidence ID(s).>

## Communication and coordination

<Conditional interpretation with inline evidence ID(s).>

## Tension, boundaries, and repair

<Conditional interpretation with inline evidence ID(s).>

## Growth and shared direction

<Conditional interpretation with inline evidence ID(s).>

## Requested or context-specific domains

<Insert only selected level-three canonical modules; leave this section without a module when none is authorized.>

## Overall synthesis

<Conditional synthesis with inline evidence ID(s).>

## Evidence index

- <Exact ledger citation, including evidence token and display string.>
```

## English conditional modules

Insert a selected module as a level-three heading under `Requested or context-specific domains`. Use only these canonical headings:

- `### Romance and intimacy`
- `### Friendship and community`
- `### Family and care`
- `### Work and creative collaboration`
- `### Money and shared resources`

Under each selected heading, write only conditional, evidence-linked paragraphs. Do not add a generic domain heading or any unselected module.

## Chinese universal report

```markdown
# 双方合盘分析：<已验证的显示标签或主体 ID>

## 分析基础、数据来源与限制

- 数据来源：已验证的合盘 JSON v2；图表 ID <chart-id>
- 计算与相位配置：计算 <configuration.calculation_profile>；相位 <configuration.aspect_profile>。
- 宫位系统与相位容许度：<configuration.house_system；未配置时写“未配置”>；主要相位 <configuration.major_orb>°；次要相位 <configuration.minor_orb>°。
- 星历数据来源：请求 <provenance.requested_backend>；实际 <provenance.actual_backend>；软件 <provenance.software_version>；绑定 <provenance.binding_version>；时区 <provenance.timezone_source>；返回标志 <以英文逗号分隔 provenance.return_flags；为空时写“无”>；警告 <以竖线分隔 provenance.warnings；为空时写“无”>。
- 用户明确提供的关系背景：未说明
- 数据限制：<每个 limitation.message 原样复制为单独一行；没有时写“未记录限制”>

## 反复出现的互动模式

<使用条件式措辞并在段内引用证据 ID。>

## 双向影响与不对称性

<保留主体归属和方向，并在段内引用证据 ID。>

## 沟通与协作

<使用条件式措辞并在段内引用证据 ID。>

## 张力、边界与修复

<使用条件式措辞并在段内引用证据 ID。>

## 成长与共同方向

<使用条件式措辞并在段内引用证据 ID。>

## 用户要求或关系背景领域

<只插入已明确授权的三级规范模块；没有授权模块时不添加模块。>

## 整体总结

<使用条件式措辞并在段内引用证据 ID。>

## 证据索引

- <完整复制证据账本中的证据标记和显示字符串。>
```

## Chinese conditional modules

Only use these level-three headings under `用户要求或关系背景领域`:

- `### 浪漫与亲密关系`
- `### 友谊与社群`
- `### 家庭与照护`
- `### 工作与创意协作`
- `### 金钱与共同资源`

## Evidence-limit form

Keep an explicitly selected weak-evidence module, but replace interpretation with this shape:

```markdown
### <Selected canonical module>

The source does not support a confident domain-specific interpretation because <specific evidence limitation>. <Cite any directly relevant available evidence ID; omit advice presented as chart-supported.>
```

Chinese form:

```markdown
### <已选择的规范模块>

源数据不足以支持有把握的领域解读，因为<具体证据限制>。<引用任何直接相关的现有证据 ID；不提供声称由星盘支持的建议。>
```
