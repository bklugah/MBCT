"""
Brain surface visualization with labeled regions
Uses nilearn and plotly for interactive 3D brain maps
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')


class BrainVisualizer:
    """Visualize brain regions with labels and color coding"""
    
    # Network coordinates (MNI space)
    NETWORK_REGIONS = {
        'Default Mode': [(-5, -52, 18), (0, -53, 26), (6, -52, 18)],
        'Visual': [(-20, -90, 0), (20, -90, 0), (0, -85, 15)],
        'Motor': [(-40, -20, 50), (40, -20, 50), (0, -15, 55)],
        'Salience': [(-35, 20, -8), (35, 20, -8), (0, 15, 0)],
        'Dorsal Attention': [(-35, -50, 45), (35, -50, 45), (0, -48, 50)],
        'Language': [(-55, -25, 15), (-50, 0, 25), (-45, 15, 10)],
        'Memory': [(-30, -35, -10), (30, -35, -10), (0, -30, 5)],
        'Cerebellar': [(-20, -60, -30), (20, -60, -30), (0, -65, -25)],
    }
    
    # White matter tract endpoints
    TRACT_PATHWAYS = {
        'Superior Longitudinal Fasciculus': [(-40, -50, 30), (-35, 20, 35)],
        'Inferior Longitudinal Fasciculus': [(-40, -70, -10), (-35, -20, -15)],
        'Arcuate Fasciculus': [(-50, -30, 25), (-45, 15, 20)],
        'Uncinate Fasciculus': [(-35, 20, -10), (-45, -30, -15)],
        'Corpus Callosum': [(-20, 0, 25), (20, 0, 25)],
        'Internal Capsule': [(-15, -10, 15), (15, -10, 15)],
        'Cingulum': [(-10, -30, 30), (10, -30, 30)],
        'Fornix': [(-5, -20, 5), (5, -20, 5)],
        'Anterior Commissure': [(-10, 5, -5), (10, 5, -5)],
        'Posterior Commissure': [(-10, -25, -5), (10, -25, -5)],
    }
    
    @staticmethod
    def create_brain_surface_visualization(networks, overlaps, title="Brain Network Map"):
        """Create 3D brain surface with labeled networks"""
        try:
            import plotly.graph_objects as go
            
            # Create figure
            fig = go.Figure()
            
            # Add brain surface (simplified sphere as base)
            u = np.linspace(0, 2 * np.pi, 50)
            v = np.linspace(0, np.pi, 50)
            x_brain = 70 * np.outer(np.cos(u), np.sin(v))
            y_brain = 70 * np.outer(np.sin(u), np.sin(v))
            z_brain = 70 * np.outer(np.ones(np.size(u)), np.cos(v))
            
            fig.add_trace(go.Surface(
                x=x_brain, y=y_brain, z=z_brain,
                colorscale='Greys',
                showscale=False,
                opacity=0.2,
                name='Brain Surface'
            ))
            
            # Add network regions as points
            colors_map = {}
            for i, (network, overlap) in enumerate(zip(networks, overlaps)):
                # Color based on overlap (green=high, orange=low)
                if overlap > 0.7:
                    color = 'rgba(128, 255, 128, 0.8)'  # Green
                else:
                    color = 'rgba(255, 170, 0, 0.8)'  # Orange
                colors_map[network] = color
                
                if network in BrainVisualizer.NETWORK_REGIONS:
                    regions = BrainVisualizer.NETWORK_REGIONS[network]
                    x_coords = [r[0] for r in regions]
                    y_coords = [r[1] for r in regions]
                    z_coords = [r[2] for r in regions]
                    
                    fig.add_trace(go.Scatter3d(
                        x=x_coords, y=y_coords, z=z_coords,
                        mode='markers+text',
                        name=f'{network} (OL: {overlap:.3f})',
                        text=[f'{network}<br>Overlap: {overlap:.3f}'] * len(regions),
                        textposition='top center',
                        marker=dict(
                            size=8,
                            color=color,
                            line=dict(width=2, color='white')
                        )
                    ))
            
            # Update layout
            fig.update_layout(
                title=dict(text=title, font=dict(size=16, color='white')),
                scene=dict(
                    xaxis=dict(title='X (Left-Right)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    yaxis=dict(title='Y (Posterior-Anterior)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    zaxis=dict(title='Z (Inferior-Superior)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    camera=dict(eye=dict(x=1.2, y=1.2, z=1.2))
                ),
                paper_bgcolor='rgba(15, 15, 30, 0.9)',
                plot_bgcolor='rgba(15, 15, 30, 0.9)',
                font=dict(color='#e0e0e0', size=11),
                height=500,
                showlegend=True,
                hovermode='closest'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating brain surface visualization: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def create_white_matter_visualization(tracts, overlaps, title="White Matter Tract Map"):
        """Create 3D visualization of white matter tracts"""
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            
            # Add brain surface
            u = np.linspace(0, 2 * np.pi, 50)
            v = np.linspace(0, np.pi, 50)
            x_brain = 70 * np.outer(np.cos(u), np.sin(v))
            y_brain = 70 * np.outer(np.sin(u), np.sin(v))
            z_brain = 70 * np.outer(np.ones(np.size(u)), np.cos(v))
            
            fig.add_trace(go.Surface(
                x=x_brain, y=y_brain, z=z_brain,
                colorscale='Greys',
                showscale=False,
                opacity=0.15,
                name='Brain Surface'
            ))
            
            # Add tract pathways
            for tract, overlap in zip(tracts, overlaps):
                if tract in BrainVisualizer.TRACT_PATHWAYS:
                    pathway = BrainVisualizer.TRACT_PATHWAYS[tract]
                    
                    # Color based on overlap
                    if overlap > 0.7:
                        color = 'rgba(0, 212, 255, 0.8)'  # Cyan
                        width = 8
                    elif overlap > 0.5:
                        color = 'rgba(100, 200, 255, 0.6)'  # Light blue
                        width = 6
                    else:
                        color = 'rgba(150, 150, 150, 0.4)'  # Gray
                        width = 4
                    
                    x_coords = [p[0] for p in pathway]
                    y_coords = [p[1] for p in pathway]
                    z_coords = [p[2] for p in pathway]
                    
                    fig.add_trace(go.Scatter3d(
                        x=x_coords, y=y_coords, z=z_coords,
                        mode='lines+markers',
                        name=f'{tract} (OL: {overlap:.3f})',
                        line=dict(color=color, width=width),
                        marker=dict(
                            size=8,
                            color=color,
                            line=dict(width=2, color='white')
                        )
                    ))
            
            # Update layout
            fig.update_layout(
                title=dict(text=title, font=dict(size=16, color='white')),
                scene=dict(
                    xaxis=dict(title='X (Left-Right)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    yaxis=dict(title='Y (Posterior-Anterior)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    zaxis=dict(title='Z (Inferior-Superior)', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    camera=dict(eye=dict(x=1.2, y=1.2, z=1.2))
                ),
                paper_bgcolor='rgba(15, 15, 30, 0.9)',
                plot_bgcolor='rgba(15, 15, 30, 0.9)',
                font=dict(color='#e0e0e0', size=11),
                height=500,
                showlegend=True,
                hovermode='closest'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating white matter visualization: {e}")
            return None
    
    @staticmethod
    def create_multimodal_brain_visualization(networks, gm_overlaps, tracts, wm_overlaps, 
                                            title="Multimodal Brain Map (Gray + White Matter)"):
        """Create combined GM and WM visualization"""
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            
            # Add brain surface
            u = np.linspace(0, 2 * np.pi, 50)
            v = np.linspace(0, np.pi, 50)
            x_brain = 70 * np.outer(np.cos(u), np.sin(v))
            y_brain = 70 * np.outer(np.sin(u), np.sin(v))
            z_brain = 70 * np.outer(np.ones(np.size(u)), np.cos(v))
            
            fig.add_trace(go.Surface(
                x=x_brain, y=y_brain, z=z_brain,
                colorscale='Greys',
                showscale=False,
                opacity=0.15,
                name='Brain Surface'
            ))
            
            # Add gray matter networks
            for network, overlap in zip(networks, gm_overlaps):
                if network in BrainVisualizer.NETWORK_REGIONS:
                    regions = BrainVisualizer.NETWORK_REGIONS[network]
                    x_coords = [r[0] for r in regions]
                    y_coords = [r[1] for r in regions]
                    z_coords = [r[2] for r in regions]
                    
                    # Green for GM
                    if overlap > 0.7:
                        color = 'rgba(128, 255, 128, 0.9)'
                    else:
                        color = 'rgba(100, 200, 100, 0.7)'
                    
                    fig.add_trace(go.Scatter3d(
                        x=x_coords, y=y_coords, z=z_coords,
                        mode='markers',
                        name=f'{network} (GM)',
                        marker=dict(size=6, color=color),
                        legendgroup='gray_matter'
                    ))
            
            # Add white matter tracts
            for tract, overlap in zip(tracts, wm_overlaps):
                if tract in BrainVisualizer.TRACT_PATHWAYS:
                    pathway = BrainVisualizer.TRACT_PATHWAYS[tract]
                    x_coords = [p[0] for p in pathway]
                    y_coords = [p[1] for p in pathway]
                    z_coords = [p[2] for p in pathway]
                    
                    # Cyan for WM
                    if overlap > 0.7:
                        color = 'rgba(0, 212, 255, 0.8)'
                        width = 6
                    else:
                        color = 'rgba(100, 200, 255, 0.5)'
                        width = 4
                    
                    fig.add_trace(go.Scatter3d(
                        x=x_coords, y=y_coords, z=z_coords,
                        mode='lines',
                        name=f'{tract} (WM)',
                        line=dict(color=color, width=width),
                        legendgroup='white_matter'
                    ))
            
            fig.update_layout(
                title=dict(text=title, font=dict(size=16, color='white')),
                scene=dict(
                    xaxis=dict(title='X', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    yaxis=dict(title='Y', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    zaxis=dict(title='Z', backgroundcolor='rgba(15, 15, 30, 0.9)',
                               gridcolor='rgba(52, 53, 72, 0.3)', color='#a0a0a0'),
                    camera=dict(eye=dict(x=1.2, y=1.2, z=1.2))
                ),
                paper_bgcolor='rgba(15, 15, 30, 0.9)',
                plot_bgcolor='rgba(15, 15, 30, 0.9)',
                font=dict(color='#e0e0e0', size=11),
                height=600,
                showlegend=True,
                hovermode='closest'
            )
            
            return fig
        except Exception as e:
            print(f"Error creating multimodal visualization: {e}")
            return None
