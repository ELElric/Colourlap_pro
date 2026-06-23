/* ============================================================
 * ColorLab Pro 代码审查报告 - 图表逻辑
 * 使用 ECharts 渲染所有数据可视化
 * ============================================================ */

(function () {
  'use strict';

  // 从 CSS 变量读取主题色
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg = style.getPropertyValue('--bg').trim();

  // 通用文字样式
  var textStyle = {
    color: ink,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
  };

  var labelStyle = {
    color: muted,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
  };

  /* ----------------------------------------------------------
   * 图表1：修复分布饼图（按优先级）
   * ---------------------------------------------------------- */
  function initPriorityPie() {
    var el = document.getElementById('chart-priority-pie');
    if (!el) return;

    var chart = echarts.init(el, null, { renderer: 'svg' });

    var pieColors = [accent2, '#ffa94d', accent, muted];

    chart.setOption({
      title: {
        text: '按优先级分布',
        left: 'center',
        top: 10,
        textStyle: {
          color: ink,
          fontSize: 15,
          fontWeight: 600
        },
        subtext: '共 57 项修复',
        subtextStyle: {
          color: muted,
          fontSize: 12
        }
      },
      tooltip: {
        trigger: 'item',
        appendToBody: true,
        formatter: '{b}: {c} 项 ({d}%)',
        backgroundColor: bg2,
        borderColor: rule,
        textStyle: textStyle
      },
      legend: {
        orient: 'horizontal',
        bottom: 10,
        left: 'center',
        textStyle: labelStyle,
        itemWidth: 14,
        itemHeight: 14,
        itemGap: 20
      },
      color: pieColors,
      animation: false,
      series: [
        {
          name: '修复分布',
          type: 'pie',
          radius: ['38%', '62%'],
          center: ['50%', '48%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderColor: bg,
            borderWidth: 2
          },
          label: {
            show: true,
            formatter: '{b}\n{c} 项',
            color: ink,
            fontSize: 12,
            lineHeight: 18
          },
          labelLine: {
            lineStyle: { color: rule }
          },
          emphasis: {
            label: { show: true, fontWeight: 600 },
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0,0,0,0.4)'
            }
          },
          data: [
            { value: 11, name: 'P0 崩溃' },
            { value: 23, name: 'P1 逻辑错误' },
            { value: 16, name: 'P2 中等问题' },
            { value: 7, name: 'P3 轻微' }
          ]
        }
      ]
    });

    window.addEventListener('resize', function () { chart.resize(); });
  }

  /* ----------------------------------------------------------
   * 图表2：修复时间线柱状图（按批次）
   * ---------------------------------------------------------- */
  function initBatchBar() {
    var el = document.getElementById('chart-batch-bar');
    if (!el) return;

    var chart = echarts.init(el, null, { renderer: 'svg' });

    var batchData = [
      { batch: '批次1', count: 2 },
      { batch: '批次2', count: 5 },
      { batch: '批次3', count: 4 },
      { batch: '批次4', count: 3 },
      { batch: '批次5', count: 1 },
      { batch: '批次6', count: 4 },
      { batch: '批次7', count: 3 },
      { batch: '批次8', count: 4 },
      { batch: '批次9', count: 3 },
      { batch: '批次10', count: 2 },
      { batch: '批次11', count: 5 },
      { batch: '批次12', count: 3 },
      { batch: '批次13', count: 4 },
      { batch: '批次14', count: 3 },
      { batch: '批次15', count: 8 },
      { batch: '批次16', count: 3 }
    ];

    chart.setOption({
      title: {
        text: '各批次修复数量',
        left: 'center',
        top: 10,
        textStyle: {
          color: ink,
          fontSize: 15,
          fontWeight: 600
        },
        subtext: '16 个批次共 57 项修复',
        subtextStyle: {
          color: muted,
          fontSize: 12
        }
      },
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        formatter: function (params) {
          var p = params[0];
          return p.name + '<br/>修复数量: <b>' + p.value + '</b> 项';
        },
        backgroundColor: bg2,
        borderColor: rule,
        textStyle: textStyle
      },
      grid: {
        left: 50,
        right: 30,
        top: 80,
        bottom: 60
      },
      xAxis: {
        type: 'category',
        data: batchData.map(function (d) { return d.batch; }),
        axisLabel: {
          color: muted,
          fontSize: 11,
          rotate: 35,
          interval: 0
        },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { lineStyle: { color: rule } }
      },
      yAxis: {
        type: 'value',
        name: '修复数量',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { lineStyle: { color: rule, type: 'dashed', opacity: 0.4 } }
      },
      animation: false,
      series: [
        {
          name: '修复数量',
          type: 'bar',
          data: batchData.map(function (d) { return d.count; }),
          barWidth: '55%',
          itemStyle: {
            color: accent,
            borderRadius: [4, 4, 0, 0]
          },
          emphasis: {
            itemStyle: {
              color: accent2
            }
          },
          label: {
            show: true,
            position: 'top',
            color: ink,
            fontSize: 11,
            fontWeight: 600
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: accent2, type: 'dashed', opacity: 0.6 },
            label: {
              color: accent2,
              fontSize: 10,
              formatter: '平均 {c}'
            },
            data: [
              {
                type: 'average',
                name: '平均'
              }
            ]
          }
        }
      ]
    });

    window.addEventListener('resize', function () { chart.resize(); });
  }

  /* ----------------------------------------------------------
   * 图表3：涉及文件修复分布（横向柱状图）
   * ---------------------------------------------------------- */
  function initFileBar() {
    var el = document.getElementById('chart-file-bar');
    if (!el) return;

    var chart = echarts.init(el, null, { renderer: 'svg' });

    var fileData = [
      { name: 'thickness_optimizer_page.py', count: 12 },
      { name: 'gamut_calculator_page.py', count: 10 },
      { name: 'spectrum_page.py', count: 9 },
      { name: 'white_point_page.py', count: 8 },
      { name: 'analyze_page.py', count: 5 },
      { name: 'spectrum_viewmodel.py', count: 3 },
      { name: 'analyze_viewmodel.py', count: 3 },
      { name: 'thickness_optimizer.py', count: 2 },
      { name: 'spectrum_service.py', count: 2 },
      { name: 'spectrum_controller.py', count: 2 },
      { name: 'cie_diagram.py', count: 2 }
    ];

    chart.setOption({
      title: {
        text: '各文件修复数量分布',
        left: 'center',
        top: 10,
        textStyle: {
          color: ink,
          fontSize: 15,
          fontWeight: 600
        },
        subtext: '共涉及 11 个源文件',
        subtextStyle: {
          color: muted,
          fontSize: 12
        }
      },
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        formatter: function (params) {
          var p = params[0];
          return p.name + '<br/>修复数量: <b>' + p.value + '</b> 项';
        },
        backgroundColor: bg2,
        borderColor: rule,
        textStyle: textStyle
      },
      grid: {
        left: 180,
        right: 50,
        top: 80,
        bottom: 30
      },
      xAxis: {
        type: 'value',
        name: '修复数量',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { lineStyle: { color: rule, type: 'dashed', opacity: 0.4 } }
      },
      yAxis: {
        type: 'category',
        data: fileData.map(function (d) { return d.name; }).reverse(),
        axisLabel: {
          color: muted,
          fontSize: 11,
          fontFamily: 'Consolas, "Courier New", monospace'
        },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { show: false }
      },
      animation: false,
      series: [
        {
          name: '修复数量',
          type: 'bar',
          data: fileData.map(function (d) { return d.count; }).reverse(),
          barWidth: '55%',
          itemStyle: {
            color: accent,
            borderRadius: [0, 4, 4, 0]
          },
          emphasis: {
            itemStyle: { color: accent2 }
          },
          label: {
            show: true,
            position: 'right',
            color: ink,
            fontSize: 11,
            fontWeight: 600
          }
        }
      ]
    });

    window.addEventListener('resize', function () { chart.resize(); });
  }

  /* ----------------------------------------------------------
   * 初始化所有图表
   * ---------------------------------------------------------- */
  function initAll() {
    initPriorityPie();
    initBatchBar();
    initFileBar();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
