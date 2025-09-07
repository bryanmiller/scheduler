import numpy as np
import matplotlib.pyplot as plt

from scheduler.core.statscalculator.run_summary import RunSummary, Summary

def plot_stats(plan_summary: RunSummary, output=''):
    """Plot statistics from a RunSummary"""

    print(plan_summary.summary)
    # print(len(plan_summary.summary))
    print(plan_summary.metrics_per_band)
    metric_txt = 'Metric sums\n'
    # for band in plan_summary.metrics_per_band.keys():
    for band in ['BAND1', 'BAND2', 'BAND3', 'BAND4']:
        if band in plan_summary.metrics_per_band.keys():
            metric_txt += f'{band} {plan_summary.metrics_per_band[band]:6.1f}\n'

    # Arrays for histograms
    cplt = []
    metrics = []
    for prog in plan_summary.summary.keys():
        c = float(plan_summary.summary[prog][0].strip('%'))/100.
        m = plan_summary.summary[prog][1]
        cplt.append(c)
        metrics.append(m)

    fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, figsize=(12, 5))
    # Completion fraction
    ax1.hist(cplt)
    ax1.set_xlabel('Completeness', fontsize=14)
    ax1.set_ylabel('Number', fontsize=14)

    # Metric
    ax2.hist(metrics)
    ax2.set_xlabel('Metric', fontsize=14)
    ax2.set_ylabel('Number', fontsize=14)
    ax2.annotate(metric_txt, (0.75, 0.65), xycoords='figure fraction', fontsize=14)

    if output == '':
        plt.show()
    else:
        plt.savefig(output, dpi=150)
