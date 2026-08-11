"""
connectivity_view.py — seed-based functional-connectivity visualisation.

A seed-based FC map is a continuous volume, not a set of edges, so discrete
"connections" are derived from it:

  seed        : the map's global maximum (a seed correlates ~1.0 with itself),
                or an MNI coordinate supplied by the user.
  targets     : peak coordinate of every supra-threshold cluster (excluding the
                cluster containing the seed), found by connected-component
                labelling — the same approach the viewer uses for cluster stats.
  connections : seed -> target, weighted by the target peak's value.

Two renderings are produced (both via nilearn on the Agg backend, saved to PNG
for display in a QLabel — never FigureCanvasQTAgg):

  overview_figure()   one glass brain: all nodes colour-coded, lines seed->target
  grid_figure()       a grid of small glass brains, one per connection
"""

import numpy as np

try:
    from scipy import ndimage
except Exception:
    ndimage = None


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def voxel_to_mni(ijk, affine):
    v = np.asarray([ijk[0], ijk[1], ijk[2], 1.0], dtype=float)
    return tuple(float(c) for c in (affine @ v)[:3])


def mni_to_voxel(xyz, affine):
    inv = np.linalg.inv(affine)
    v = inv @ np.asarray([xyz[0], xyz[1], xyz[2], 1.0], dtype=float)
    return tuple(int(round(c)) for c in v[:3])


# --------------------------------------------------------------------------
# node / connection extraction
# --------------------------------------------------------------------------
def find_seed(data, affine):
    """Seed = global maximum of the FC map (|value| max)."""
    d = np.nan_to_num(np.asarray(data, dtype=np.float32))
    idx = np.unravel_index(np.argmax(np.abs(d)), d.shape)
    return voxel_to_mni(idx, affine), float(d[idx])


def extract_connections(data, affine, threshold=0.3, min_extent=20,
                        seed_mni=None, max_targets=12, exclude_radius=12.0):
    """Derive connectome nodes/edges from a seed-based FC volume.

    Returns (seed_xyz, [ {xyz, value, size} ... ]) sorted by |value| desc.
    """
    if ndimage is None:
        raise RuntimeError("scipy is required for connectivity extraction")

    d = np.nan_to_num(np.asarray(data, dtype=np.float32))

    if seed_mni is None:
        seed_mni, _ = find_seed(d, affine)
    seed_mni = tuple(float(c) for c in seed_mni)

    mask = np.abs(d) >= float(threshold)
    if not mask.any():
        return seed_mni, []

    lab, n = ndimage.label(mask)          # 26-connectivity default is 6; fine here
    targets = []
    for cid in range(1, n + 1):
        sel = (lab == cid)
        size = int(sel.sum())
        if size < int(min_extent):
            continue
        vals = np.where(sel, np.abs(d), 0.0)
        pk = np.unravel_index(np.argmax(vals), d.shape)
        xyz = voxel_to_mni(pk, affine)
        # skip the cluster that contains (or sits on top of) the seed
        dist = float(np.linalg.norm(np.asarray(xyz) - np.asarray(seed_mni)))
        if dist < float(exclude_radius):
            continue
        targets.append({'xyz': xyz, 'value': float(d[pk]), 'size': size})

    targets.sort(key=lambda t: abs(t['value']), reverse=True)
    return seed_mni, targets[:int(max_targets)]


def build_adjacency(seed_xyz, targets):
    """Node coordinate list + adjacency matrix for nilearn.plot_connectome.

    Node 0 is the seed; every edge runs seed -> target_i.
    """
    coords = [list(seed_xyz)] + [list(t['xyz']) for t in targets]
    n = len(coords)
    adj = np.zeros((n, n), dtype=float)
    for i, t in enumerate(targets, start=1):
        adj[0, i] = adj[i, 0] = float(t['value'])
    return np.asarray(coords, dtype=float), adj


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _labels_for(xyz):
    """Anatomical label for a coordinate: gray-matter region (+ WM tract)."""
    gm = wm = None
    try:
        import anatomy_lookup as anat
        gm = (anat.label_at_mni(*xyz) or {}).get('region')
    except Exception:
        pass
    try:
        import whitematter_lookup as wml
        info = wml.wm_label_at_mni(*xyz) or {}
        wm = info.get('region') if info.get('region') not in (None, '—') else info.get('tract')
        if wm == '—':
            wm = None
    except Exception:
        pass
    return gm, wm


def overview_figure(seed_xyz, targets, figsize=(9, 3.2), node_size=55,
                    title=None):
    """One glass brain: seed + targets, lines weighted by connection strength."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from nilearn import plotting as niplot

    coords, adj = build_adjacency(seed_xyz, targets)
    # seed drawn larger and in a distinct colour
    colors = ['#39ff14'] + ['#ff5252' if t['value'] > 0 else '#38b6ff'
                            for t in targets]
    sizes = [node_size * 1.8] + [node_size] * len(targets)

    fig = plt.figure(figsize=figsize, facecolor='black')
    niplot.plot_connectome(
        adj, coords, figure=fig, display_mode='lyrz',
        node_color=colors, node_size=sizes,
        edge_threshold=None, black_bg=True,
        colorbar=False, annotate=False,
        title=title)
    return fig


def grid_figure(seed_xyz, targets, ncols=3, panel_size=(3.0, 1.5),
                annotate_labels=True):
    """A grid of small glass brains — one per seed->target connection."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from nilearn import plotting as niplot

    n = len(targets)
    if n == 0:
        return None
    ncols = max(1, int(ncols))
    nrows = int(np.ceil(n / ncols))
    fig = plt.figure(
        figsize=(panel_size[0] * ncols, panel_size[1] * nrows),
        facecolor='black')

    for i, t in enumerate(targets):
        ax = fig.add_subplot(nrows, ncols, i + 1)
        ax.set_facecolor('black')
        coords = np.asarray([list(seed_xyz), list(t['xyz'])], dtype=float)
        adj = np.zeros((2, 2), dtype=float)
        adj[0, 1] = adj[1, 0] = float(t['value'])
        edge_c = '#ff5252' if t['value'] > 0 else '#38b6ff'
        try:
            niplot.plot_connectome(
                adj, coords, axes=ax, display_mode='z',
                node_color=['#39ff14', edge_c], node_size=38,
                black_bg=True, colorbar=False, annotate=False)
        except Exception:
            ax.axis('off')

        if annotate_labels:
            gm, wm = _labels_for(t['xyz'])
            name = gm or wm or "unlabelled"
            x, y, z = (round(c) for c in t['xyz'])
            ax.set_title(f"{name}\nr={t['value']:.2f}  ({x}, {y}, {z})",
                         color='#e6e9ef', fontsize=7, pad=4)

    fig.patch.set_facecolor('black')
    fig.tight_layout()
    return fig


def connection_table(seed_xyz, targets):
    """Rows describing each connection, for a table/CSV export."""
    rows = []
    for t in targets:
        gm, wm = _labels_for(t['xyz'])
        x, y, z = (round(c, 1) for c in t['xyz'])
        rows.append({
            'x': x, 'y': y, 'z': z,
            'r': round(t['value'], 3),
            'voxels': t['size'],
            'region': gm or '—',
            'white_matter': wm or '—',
        })
    return rows
