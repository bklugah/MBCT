"""Visualization engine for NCT - Professional, interactive version"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


# Professional color palette
PROFESSIONAL_COLORS = {
    'bg_dark': '#0f0f1e',
    'bg_light': '#1e1e2e',
    'accent_blue': '#00d4ff',
    'accent_green': '#00ff00',
    'accent_orange': '#ffaa00',
    'text_light': '#e0e0e0',
    'text_dim': '#a0a0a0',
}


def _empty_fig(title, message="No data available"):
    """Return a professional placeholder figure"""
    fig, ax = plt.subplots(figsize=(10, 8), facecolor='white')
    ax.set_facecolor('#f8f9fa')
    ax.text(0.5, 0.5, message, ha='center', va='center',
            transform=ax.transAxes, fontsize=14, color='#666666',
            style='italic', weight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold',
                 color='#333333', pad=20)
    ax.axis('off')
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    return fig


class Visualizer:
    """Visualization engine — all methods are crash-safe"""

    @staticmethod
    def create_heatmap(heatmap_data, networks, title="Overlap Matrix Heatmap"):
        """Create heatmap visualization"""
        if not networks or not heatmap_data:
            return _empty_fig(title)

        try:
            fig, ax = plt.subplots(figsize=(8, 8), facecolor='#0f0f1e')
            ax.set_facecolor('#0f0f1e')

            data = np.array(heatmap_data)
            im = ax.imshow(data, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')

            ax.set_xticks(np.arange(len(networks)))
            ax.set_yticks(np.arange(len(networks)))
            ax.set_xticklabels(networks, rotation=45, ha='right',
                               fontsize=9, color='#e0e0e0')
            ax.set_yticklabels(networks, fontsize=9, color='#e0e0e0')
            ax.tick_params(colors='#e0e0e0')
            ax.set_title(title, fontsize=12, fontweight='bold',
                         color='#e0e0e0', pad=14)
            fig.colorbar(im, ax=ax, label='Overlap')
            plt.tight_layout()
            return fig
        except Exception as e:
            print(f"⚠️ Heatmap error: {e}")
            return _empty_fig(title, f"Visualization error: {e}")

    @staticmethod
    def create_clock_map(overlaps, networks, title="Network Overlap - Clock Map"):
        """Create clock/radar map visualization"""
        if not overlaps or len(overlaps) == 0 or not networks:
            return _empty_fig(title, "No overlap data available")

        try:
            fig = plt.figure(figsize=(8, 8), facecolor='#0f0f1e')
            ax = fig.add_subplot(111, projection='polar')
            ax.set_facecolor('#0f0f1e')

            angles = np.linspace(0, 2*np.pi, len(networks), endpoint=False).tolist()
            overlaps_plot = list(overlaps) + [overlaps[0]]
            angles += [angles[0]]

            ax.plot(angles, overlaps_plot, 'o-', linewidth=2,
                    color='#00d4ff', markersize=8)
            ax.fill(angles, overlaps_plot, alpha=0.25, color='#00d4ff')
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(networks, fontsize=9, color='#e0e0e0')
            ax.set_ylim(0, 1)
            ax.set_title(title, fontsize=12, fontweight='bold',
                         color='#e0e0e0', pad=20)
            ax.grid(True, alpha=0.3, color='#444')
            ax.tick_params(colors='#e0e0e0')
            plt.tight_layout()
            return fig
        except Exception as e:
            print(f"⚠️ Clock map error: {e}")
            return _empty_fig(title, f"Visualization error: {e}")

    @staticmethod
    def create_radar_plot(overlaps, networks, title="Network Comparison - Radar Plot"):
        """Create radar plot visualization"""
        if not overlaps or len(overlaps) == 0 or not networks:
            return _empty_fig(title, "No overlap data available")

        try:
            fig = plt.figure(figsize=(8, 8), facecolor='#0f0f1e')
            ax = fig.add_subplot(111, projection='polar')
            ax.set_facecolor('#0f0f1e')

            angles = np.linspace(0, 2*np.pi, len(networks), endpoint=False).tolist()
            overlaps_plot = list(overlaps) + [overlaps[0]]
            angles += [angles[0]]

            ax.plot(angles, overlaps_plot, 'o-', linewidth=2.5,
                    color='#0099ff', markersize=10)
            ax.fill(angles, overlaps_plot, alpha=0.2, color='#0099ff')
            ax.plot(angles, [0.5]*len(angles), '--', linewidth=1,
                    color='gray', alpha=0.5, label='0.5 threshold')
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(networks, fontsize=9, color='#e0e0e0')
            ax.set_ylim(0, 1)
            ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
            ax.set_title(title, fontsize=12, fontweight='bold',
                         color='#e0e0e0', pad=20)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1),
                      labelcolor='#e0e0e0')
            ax.grid(True, alpha=0.3, color='#444')
            ax.tick_params(colors='#e0e0e0')
            plt.tight_layout()
            return fig
        except Exception as e:
            print(f"⚠️ Radar plot error: {e}")
            return _empty_fig(title, f"Visualization error: {e}")

    @staticmethod
    def create_bar_chart(overlaps, networks, title="Network Overlaps"):
        """Create professional bar chart with network names"""
        if not overlaps or len(overlaps) == 0 or not networks:
            return _empty_fig(title, "No overlap data available")

        try:
            fig, ax = plt.subplots(figsize=(12, max(8, len(networks)*0.4)), facecolor='white')
            ax.set_facecolor('#f8f9fa')

            # Create color gradient based on values
            colors = plt.cm.RdYlGn(np.linspace(0.2, 0.9, len(overlaps)))
            
            y_pos = np.arange(len(networks))
            bars = ax.barh(y_pos, overlaps, color=colors, alpha=0.85, 
                          edgecolor='#333333', linewidth=1.5)

            # Threshold line
            ax.axvline(x=0.5, color='#ff6b6b', linestyle='--', linewidth=2,
                      alpha=0.7, label='Significance threshold (0.5)')
            
            # Labels and formatting
            ax.set_yticks(y_pos)
            ax.set_yticklabels(networks, fontsize=10, color='#333333')
            ax.set_xlabel('Overlap (Dice)', fontsize=12, fontweight='bold', color='#333333')
            ax.set_title(title, fontsize=14, fontweight='bold', color='#333333', pad=20)
            ax.set_xlim(0, 1.1)
            
            # Grid
            ax.grid(axis='x', alpha=0.3, linestyle=':', color='#999999')
            ax.set_axisbelow(True)
            
            # Value labels
            for bar, val in zip(bars, overlaps):
                ax.text(val + 0.02, bar.get_y() + bar.get_height()/2,
                       f'{val:.3f}', va='center', fontsize=9, 
                       fontweight='bold', color='#333333')
            
            # Professional legend
            ax.legend(loc='lower right', fontsize=10, framealpha=0.95,
                     edgecolor='#cccccc')
            
            # Styling
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#cccccc')
            ax.spines['bottom'].set_color('#cccccc')
            ax.tick_params(colors='#333333', labelsize=10)

            plt.tight_layout()
            return fig
        except Exception as e:
            print(f"⚠️ Bar chart error: {e}")
            return _empty_fig(title, f"Visualization error: {e}")
