"""
Professional Interactive Brain Visualization Engine — NCT
---------------------------------------------------------
• Real atlas parcellation rendering  (Axial · Coronal · Sagittal)
• Synthetic MNI-estimated fallback when atlas NIfTI unavailable
• Per-network distinct colours, fully interactive
• Click row → crosshair jumps to network centroid + MNI label
• Overlap + significance bar chart
• Network colour legend
• Export: NIfTI · PNG · TIF · JPEG · CSV
"""

import numpy as np
import nibabel as nib
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
from pathlib import Path
import warnings

# Suppress font warnings for emojis (though we now use text)
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

from .network_knowledge_base import format_network_info

# ─── Colour palette ──────────────────────────────────────────────────────────

_P20 = [
    '#e63946', '#f4a261', '#2a9d8f', '#457b9d', '#a8dadc',
    '#e9c46a', '#e76f51', '#06d6a0', '#118ab2', '#ffd166',
    '#8338ec', '#fb5607', '#3a86ff', '#ff006e', '#06ffa5',
    '#ffbe0b', '#b5179e', '#4cc9f0', '#52b788', '#f72585',
]

def _build_network_colors(n):
    """Return list of n hex colour strings optimised for dark backgrounds."""
    if n == 0:
        return []
    if n <= 20:
        return [_P20[i % 20] for i in range(n)]
    cmap = plt.cm.nipy_spectral
    return [matplotlib.colors.to_hex(cmap(i / max(n - 1, 1))) for i in range(n)]

def _hex_rgb(h):
    return np.array(matplotlib.colors.to_rgb(h), dtype=np.float32)


# ─── Anatomical MNI hints ────────────────────────────────────────────────────

_MNI_HINTS = {
    'visual':       (0, -86, 4),    'visspatial':   (28, -60, 44),
    'motor':        (0, -24, 56),   'somatosensory':(0, -32, 60),
    'default':      (0, -52, 28),   'dmn':          (-2, -58, 28),
    'salience':     (40, 18, 0),    'control':      (46, 18, 38),
    'frontoparietal':(46, 30, 26),  'attention':    (30, -56, 48),
    'language':     (54, -36, 12),  'auditory':     (60, -18, 8),
    'memory':       (28, -20, -16), 'cerebellar':   (20, -58, -32),
    'intero':       (2, -18, 40),   'emo':          (4, 14, -12),
    'divergentcog': (46, 22, 28),   'limbic':       (24, 4, -24),
    'subcortical':  (16, -4, -12),  'cingulate':    (2, -4, 40),
    'temporal':     (54, -10, -16), 'prefrontal':   (36, 50, 14),
}

def _mni_hint(name):
    nm = name.lower().replace('/', '').replace(' ', '').replace('_', '')
    for key, xyz in _MNI_HINTS.items():
        if key in nm:
            return np.array(xyz, dtype=float)
    return np.array([0.0, 0.0, 0.0])


# ─── Atlas Loader ────────────────────────────────────────────────────────────

class AtlasLoader:
    """Finds and loads atlas parcellation, MNI template, and network assignment."""

    def __init__(self, cbig_obj):
        self.cbig = cbig_obj

    def load(self, atlas_code, space):
        result = dict(
            atlas_data=None, template_data=None,
            affine=self._default_affine(space),
            net_assign=None, atlas_path=None, template_path=None,
        )

        # Template
        tpl = self.cbig.find_template(space)
        if tpl:
            try:
                img = nib.load(tpl)
                result['template_data'] = np.asarray(img.get_fdata(), dtype=np.float32)
                result['affine'] = img.affine
                result['template_path'] = tpl
                print(f"  ✅ Template: {Path(tpl).name}  {result['template_data'].shape}")
            except Exception as e:
                print(f"  ⚠️ Template load failed: {e}")

        # Atlas parcellation
        atl = self.cbig.find_atlas_nifti(atlas_code, space)
        if atl:
            try:
                img = nib.load(atl)
                result['atlas_data'] = np.asarray(img.get_fdata(), dtype=np.int32)
                result['affine'] = img.affine
                result['atlas_path'] = atl
                print(f"  ✅ Atlas parcellation: {Path(atl).name}  {result['atlas_data'].shape}")
            except Exception as e:
                print(f"  ⚠️ Atlas load failed: {e}")

        # Network assignment
        na = self.cbig.load_network_assignment(atlas_code)
        if na is not None:
            result['net_assign'] = na
            print(f"  ✅ Network assignment: {len(na)} parcels")

        return result

    @staticmethod
    def _default_affine(space):
        if space == 'FSLMNI2mm':
            return np.array([[-2,0,0,90],[0,2,0,-126],[0,0,2,-72],[0,0,0,1]], float)
        return np.eye(4, float)


# ─── Brain Renderer ──────────────────────────────────────────────────────────

class BrainRenderer:
    """
    Professional triplanar brain map with coloured network overlays.
    Works with real atlas NIfTI or synthetic MNI-estimated blobs.
    """

    def __init__(self, atlas_assets, network_names, overlap_values,
                 overlap_metric='Dice', p_values=None):
        self.template   = atlas_assets.get('template_data')
        self.atlas      = atlas_assets.get('atlas_data')
        self.affine     = atlas_assets['affine']
        self.net_assign = atlas_assets.get('net_assign')

        self.names    = list(network_names)
        self.overlaps = np.array(overlap_values, dtype=float)
        self.p_values = np.array(p_values, dtype=float) if p_values is not None else None
        self.metric   = overlap_metric
        self.n_nets   = len(self.names)

        self.net_colors  = _build_network_colors(self.n_nets)
        self.highlighted = None
        self._color_cache = {}

        # Determine 3-D shape
        if self.atlas is not None:
            self.shape = self.atlas.shape[:3]
        elif self.template is not None:
            self.shape = self.template.shape[:3]
        else:
            self.shape = (91, 109, 91)

        cx, cy, cz = [s // 2 for s in self.shape]
        self.crosshair = np.array([cx, cy, cz], dtype=int)

        # Build network volume (parcellation → network index)
        self._net_vol = self._build_network_volume()
        self.centroids = self._compute_centroids()

        print(f"✅ BrainRenderer: {self.n_nets} networks | "
              f"atlas={'yes' if self.atlas is not None else 'synthetic'} | "
              f"template={'yes' if self.template is not None else 'no'}")

    # ── Public API ────────────────────────────────────────────────────────────

    def set_highlight(self, network_idx):
        self.highlighted = network_idx
        if network_idx is not None and network_idx in self.centroids:
            self.crosshair = self.centroids[network_idx]['vox'].copy()
        self._color_cache.clear()

    def get_mni(self):
        v = np.append(self.crosshair.astype(float), 1.0)
        return (self.affine @ v)[:3]

    def render(self, fig):
        """Render the full triplanar + detail panel layout into fig."""
        fig.clear()
        fig.patch.set_facecolor('#0a0a14')

        # GridSpec: 2 rows, 3 columns (triplanar on top, detail on bottom, full width)
        gs = GridSpec(
            2, 3,
            figure=fig,
            left=0.04, right=0.99,
            top=0.93, bottom=0.08,
            hspace=0.30, wspace=0.10,
            height_ratios=[3.5, 1.2],  # Brain map MUCH bigger, detail smaller
            width_ratios=[3, 3, 3],    # Equal widths for triplanar
        )

        ax_ax  = fig.add_subplot(gs[0, 0])   # Axial
        ax_cor = fig.add_subplot(gs[0, 1])   # Coronal
        ax_sag = fig.add_subplot(gs[0, 2])   # Sagittal
        ax_detail = fig.add_subplot(gs[1, :]) # Detail panel (full width)

        cx, cy, cz = [int(np.clip(self.crosshair[i], 0, self.shape[i]-1)) for i in range(3)]
        mni = self.get_mni()

        color_vol = self._get_color_volume()
        t_norm    = self._norm_template()

        self._draw_view(ax_ax,  self._axial_slices(t_norm, color_vol, cz),
                        f'Axial  Z={mni[2]:.0f} mm', 'X (L→R)', 'Y (P→A)',
                        cx, cy)
        self._draw_view(ax_cor, self._coronal_slices(t_norm, color_vol, cy),
                        f'Coronal  Y={mni[1]:.0f} mm', 'X (L→R)', 'Z (I→S)',
                        cx, cz)
        self._draw_view(ax_sag, self._sagittal_slices(t_norm, color_vol, cx),
                        f'Sagittal  X={mni[0]:.0f} mm', 'Y (P→A)', 'Z (I→S)',
                        cy, cz)

        # Label for highlighted network
        if self.highlighted is not None and self.highlighted < self.n_nets:
            name = self.names[self.highlighted]
            for ax in (ax_ax, ax_cor, ax_sag):
                ax.set_title(ax.get_title() + f'\n[{name}]',
                             color='#7dd3fc', fontsize=8.5, fontweight='bold', pad=3)

        # Draw detail panel with functional description and literature
        self._draw_network_detail(ax_detail, self.highlighted)

        # No suptitle – we use a separate info box below the figure (handled by nct_desktop_app.py)

        fig.canvas.draw_idle()

    # ── Slice helpers ─────────────────────────────────────────────────────────

    def _norm_template(self):
        if self.template is None:
            return None
        t = self.template.astype(float)
        m = np.percentile(t[t > 0], 98) if np.any(t > 0) else 1.0
        return np.clip(t / max(m, 1e-9), 0, 1)

    def _axial_slices(self, t_norm, color_vol, cz):
        t  = t_norm[:, :, cz].T if t_norm is not None else None
        cv = color_vol[:, :, cz].transpose(1, 0, 2)
        return t, cv

    def _coronal_slices(self, t_norm, color_vol, cy):
        t  = t_norm[:, cy, :].T if t_norm is not None else None
        cv = color_vol[:, cy, :].transpose(1, 0, 2)
        return t, cv

    def _sagittal_slices(self, t_norm, color_vol, cx):
        t  = t_norm[cx, :, :].T if t_norm is not None else None
        cv = color_vol[cx, :, :].transpose(1, 0, 2)
        return t, cv

    def _draw_view(self, ax, slices, title, xlabel, ylabel, crosshair_x, crosshair_y):
        ax.set_facecolor('#060610')
        t_slice, c_slice = slices

        if t_slice is not None:
            ax.imshow(t_slice, cmap='gray', origin='lower', aspect='equal',
                      interpolation='bilinear', vmin=0, vmax=1)
        else:
            # Draw synthetic brain outline
            H, W = c_slice.shape[:2]
            ax.set_xlim(0, W); ax.set_ylim(0, H)
            cx_e, cy_e = W / 2, H / 2
            rx, ry = W * 0.42, H * 0.48
            theta = np.linspace(0, 2 * np.pi, 300)
            xs = cx_e + rx * np.cos(theta)
            ys = cy_e + ry * np.sin(theta) * (1 + 0.08 * np.cos(2 * theta))
            ax.fill(xs, ys, color='#1a1a28', zorder=0)
            ax.plot(xs, ys, color='#333355', lw=1.0, zorder=1)

        ax.imshow(c_slice, origin='lower', aspect='equal',
                  interpolation='nearest', alpha=0.82)

        # Crosshair
        ax.axhline(crosshair_y, color='#00ffee', lw=0.9, alpha=0.9, zorder=10)
        ax.axvline(crosshair_x, color='#00ffee', lw=0.9, alpha=0.9, zorder=10)
        ax.plot(crosshair_x, crosshair_y, 'o', color='#ffffff',
                ms=4, mew=1.2, mec='#00ffee', zorder=11)

        ax.set_title(title, color='#c8d8f0', fontsize=8.5, fontweight='bold', pad=3)
        ax.set_xlabel(xlabel, color='#6070a0', fontsize=7.5)
        ax.set_ylabel(ylabel, color='#6070a0', fontsize=7.5)
        ax.tick_params(colors='#404060', labelsize=6)
        for spine in ax.spines.values():
            spine.set_color('#1e2240')

    # ── Network detail panel (description + PubMed references) ────────────────

    def _draw_network_detail(self, ax, highlighted):
        """Draw network functional description and literature references."""
        ax.set_facecolor('#0a0a14')
        ax.axis('off')
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)

        if highlighted is None or highlighted >= self.n_nets:
            ax.text(50, 50, '<-- Click a network row to view functional description and PubMed links',
                    ha='center', va='center', fontsize=13, color='#505080',
                    transform=ax.transAxes, weight='bold')
            return

        network_name = self.names[highlighted]
        info = format_network_info(network_name)
        
        pv = float(self.p_values[highlighted]) if self.p_values is not None else None
        ov = float(self.overlaps[highlighted])
        sig = ('★★★' if pv < 0.001 else '★★' if pv < 0.01 else '★' if pv < 0.05 else '')

        color = self.net_colors[highlighted]
        
        ax.text(3, 96, f'⊙ {network_name}',
                fontsize=16, fontweight='bold', color=color,
                ha='left', va='top', transform=ax.transAxes)
        
        ax.text(97, 96, f'{self.metric}: {ov:.5f}  {sig}',
                fontsize=12, fontweight='bold', color='#fde68a',
                ha='right', va='top', transform=ax.transAxes)

        ax.plot([2, 98], [92, 92], color='#3a5a8a', lw=2.5, transform=ax.transAxes)

        y_pos = 87
        ax.text(3, y_pos, 'Functional Role:',
                fontsize=12, fontweight='bold', color='#38b6ff',
                ha='left', va='top', transform=ax.transAxes)

        desc = info['function']
        ax.text(5, y_pos - 4.5, desc,
                fontsize=10.5, color='#d0d8f0', ha='left', va='top',
                transform=ax.transAxes, wrap=True,
                bbox=dict(boxstyle='round,pad=1.2', facecolor='#0f1a2a',
                          edgecolor='#3a6a9a', linewidth=2))

        papers = info.get('papers', [])
        y_papers = 53
        ax.text(3, y_papers, 'Landmark Studies:',
                fontsize=12, fontweight='bold', color='#38b6ff',
                ha='left', va='top', transform=ax.transAxes)

        y = y_papers - 5
        if papers:
            for i, paper in enumerate(papers[:5]):
                pmid = paper['pmid']
                ax.text(4, y, f'PMID: {pmid}',
                        fontsize=10, color='#4ade80', ha='left', va='top',
                        family='monospace', fontweight='bold',
                        transform=ax.transAxes,
                        bbox=dict(boxstyle='round,pad=0.6', facecolor='#0d2a0d',
                                  edgecolor='#4ade80', linewidth=2))
                
                author = paper['author']
                year = paper['year']
                title = paper['title']
                journal = paper.get('journal', '')
                
                citation = f"{author} ({year}) — {title}"
                if journal:
                    citation += f" · {journal}"
                
                ax.text(28, y, citation,
                        fontsize=9.5, color='#c8d8e8', ha='left', va='top',
                        transform=ax.transAxes)
                y -= 7
        else:
            ax.text(5, y, 'No literature available for this network yet.',
                    fontsize=10, color='#606080', ha='left', va='top',
                    transform=ax.transAxes, style='italic')

        search_term = info.get('search_term', network_name.lower())
        ax.text(3, y - 2, f'Search PubMed: {search_term}',
                fontsize=10, color='#6dd5ff', ha='left', va='top',
                transform=ax.transAxes, weight='bold',
                bbox=dict(boxstyle='round,pad=0.8', facecolor='#0f2a40',
                          edgecolor='#4a8acc', linewidth=2))

    # ── Volume builders ───────────────────────────────────────────────────────

    def _build_network_volume(self):
        if self.atlas is None:
            X, Y, Z = self.shape
            vol = np.zeros((X, Y, Z), dtype=np.int32)
            inv_aff = np.linalg.inv(self.affine)
            for ni, name in enumerate(self.names):
                mni = _mni_hint(name)
                vox = (inv_aff @ np.append(mni, 1.0))[:3].astype(int)
                vox = np.clip(vox, 0, np.array(self.shape) - 1)
                r = 4
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        for dz in range(-r, r + 1):
                            if dx*dx + dy*dy + dz*dz <= r*r:
                                x = np.clip(vox[0]+dx, 0, X-1)
                                y = np.clip(vox[1]+dy, 0, Y-1)
                                z = np.clip(vox[2]+dz, 0, Z-1)
                                if vol[x, y, z] == 0:
                                    vol[x, y, z] = ni + 1
            return vol

        X, Y, Z = self.shape
        net_vol  = np.zeros((X, Y, Z), dtype=np.int32)
        for lbl in np.unique(self.atlas):
            if lbl <= 0:
                continue
            mask = (self.atlas == lbl)
            pi   = int(lbl) - 1
            if self.net_assign is not None and pi < len(self.net_assign):
                ni = int(self.net_assign[pi])
            else:
                ni = pi % max(self.n_nets, 1)
            ni = max(0, min(ni, self.n_nets - 1))
            net_vol[mask] = ni + 1
        return net_vol

    def _get_color_volume(self):
        key = self.highlighted
        if key in self._color_cache:
            return self._color_cache[key]

        X, Y, Z = self.shape
        vol = np.zeros((X, Y, Z, 4), dtype=np.float32)

        for ni in range(self.n_nets):
            mask = (self._net_vol == ni + 1)
            if not np.any(mask):
                continue
            rgb   = _hex_rgb(self.net_colors[ni])
            alpha = 0.78

            if self.highlighted is not None:
                if ni == self.highlighted:
                    alpha = 1.0
                    rgb   = np.clip(rgb * 0.65 + 0.35, 0, 1)
                else:
                    alpha = 0.14

            vol[mask, :3] = rgb
            vol[mask,  3] = alpha

        self._color_cache[key] = vol
        return vol

    def _compute_centroids(self):
        centroids = {}
        inv_aff   = np.linalg.inv(self.affine)

        for ni in range(self.n_nets):
            mask   = (self._net_vol == ni + 1)
            voxels = np.argwhere(mask)

            if len(voxels) == 0:
                mni = _mni_hint(self.names[ni])
                vox = np.clip(
                    (inv_aff @ np.append(mni, 1.0))[:3].astype(int),
                    0, np.array(self.shape) - 1,
                )
            else:
                vox = np.clip(
                    voxels.mean(axis=0).astype(int),
                    0, np.array(self.shape) - 1,
                )

            mni = (self.affine @ np.append(vox.astype(float), 1.0))[:3]
            centroids[ni] = {'vox': vox, 'mni': mni}

        return centroids


# ─── Export Manager ───────────────────────────────────────────────────────────

class ExportManager:
    """Export results as CSV, NIfTI, PNG, TIF, JPEG."""

    @staticmethod
    def export_csv(results, output_path):
        try:
            import pandas as pd
            networks = results.get('networks', [])
            overlaps = results.get('overlaps', [])
            p_values = results.get('p_values', [])
            metric   = results.get('overlap_metric', 'Dice')
            atlas    = results.get('atlas_code', '')
            space    = results.get('brain_space', '')
            n = min(len(networks), len(overlaps), len(p_values))

            sigs = []
            for p in p_values[:n]:
                if   p < 0.001: sigs.append('***')
                elif p < 0.01:  sigs.append('**')
                elif p < 0.05:  sigs.append('*')
                else:            sigs.append('n.s.')

            df = pd.DataFrame({
                'Name':        networks[:n],
                metric:        [round(v, 6) for v in overlaps[:n]],
                'P-value':     [round(p, 6) for p in p_values[:n]],
                'Significance': sigs,
                'Atlas':       [atlas] * n,
                'Space':       [space] * n,
            })
            df.to_csv(output_path, index=False)
            print(f"✅ CSV exported ({n} rows) → {output_path}")
            return True
        except Exception as e:
            print(f"❌ CSV export error: {e}")
            import traceback; traceback.print_exc()
            return False

    @staticmethod
    def export_nifti(results, output_path, renderer=None):
        try:
            overlaps = np.array(results.get('overlaps', []))
            space    = results.get('brain_space', 'FSLMNI2mm')

            if renderer is not None and renderer.atlas is not None:
                X, Y, Z = renderer.atlas.shape[:3]
                data    = np.zeros((X, Y, Z), dtype=np.float32)
                affine  = renderer.affine
                for ni in range(renderer.n_nets):
                    if ni >= len(overlaps): break
                    mask = (renderer._net_vol == ni + 1)
                    data[mask] = float(overlaps[ni])
            elif renderer is not None:
                X, Y, Z = renderer.shape
                data    = np.zeros((X, Y, Z), dtype=np.float32)
                affine  = renderer.affine
                for ni in range(renderer.n_nets):
                    if ni >= len(overlaps): break
                    mask = (renderer._net_vol == ni + 1)
                    data[mask] = float(overlaps[ni])
            else:
                if space == 'FSLMNI2mm':
                    X, Y, Z = 91, 109, 91
                    affine  = np.array([[-2,0,0,90],[0,2,0,-126],[0,0,2,-72],[0,0,0,1]], float)
                else:
                    X, Y, Z = 100, 100, 100
                    affine  = np.eye(4)
                data = np.zeros((X, Y, Z), dtype=np.float32)

            nib.save(nib.Nifti1Image(data, affine), output_path)
            print(f"✅ NIfTI exported → {output_path}")
            return True
        except Exception as e:
            print(f"❌ NIfTI export error: {e}")
            import traceback; traceback.print_exc()
            return False

    @staticmethod
    def export_image(fig, output_path, fmt='png', dpi=150, renderer=None):
        """
        Export the brain map as an image.
        If renderer is provided, create a fresh figure and render into it to avoid size issues.
        """
        try:
            if fig is None and renderer is None:
                print("❌ No figure or renderer to export")
                return False

            # If we have a renderer, create a temporary figure with safe size
            if renderer is not None:
                temp_fig = plt.Figure(figsize=(12, 8), facecolor='#0a0a14')
                renderer.render(temp_fig)
                target_fig = temp_fig
            else:
                target_fig = fig

            ext_map = {'jpg': 'jpeg', 'tif': 'tiff'}
            fmt_out = ext_map.get(fmt.lower(), fmt.lower())

            # Save directly (no size modifications needed)
            target_fig.savefig(output_path, format=fmt_out, dpi=dpi,
                               bbox_inches='tight', facecolor=target_fig.get_facecolor())

            # If we used a temporary figure, close it to free memory
            if renderer is not None:
                plt.close(target_fig)

            print(f"✅ {fmt.upper()} exported (dpi={dpi}) → {output_path}")
            return True
        except Exception as e:
            print(f"❌ Image export error: {e}")
            import traceback
            traceback.print_exc()
            return False