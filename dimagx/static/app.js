document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    
    const colors = {
        'Project': '#00d2ff',
        'File': '#3b82f6',
        'Feature': '#f59e0b',
        'PRD': '#a855f7',
        'Commit': '#10b981',
        'Decision': '#ef4444',
        'Prompt': '#ec4899',
        'Entity': '#38bdf8'
    };

    let graphData = { nodes: [], links: [] };
    let graph;

    const graphContainer = document.getElementById('graph-container');
    const detailsPanel = document.getElementById('details-panel');
    const searchInput = document.getElementById('search-input');
    const resetViewBtn = document.getElementById('reset-view');
    const closePanelBtn = document.getElementById('close-panel');
    let is3D = false;

    // Initialize graph
    function initGraph(data) {
        graphContainer.innerHTML = ''; // Clear container
        
        graph = (is3D ? ForceGraph3D() : ForceGraph())(graphContainer)
            .nodeId('id')
            .nodeLabel(node => {
                const title = node.properties.title || node.properties.path || node.id;
                return `<div class="tooltip"><strong>${node.label}</strong><br/>${title}</div>`;
            })
            .nodeColor(node => colors[node.label] || '#999')
            .nodeRelSize(is3D ? 4 : 6)
            .linkDirectionalArrowLength(4)
            .linkDirectionalArrowRelPos(1)
            .linkCurvature(0.15)
            .linkColor(() => 'rgba(255, 255, 255, 0.15)')
            .onNodeClick(node => {
                showNodeDetails(node);
                if (is3D) {
                    const distance = 120;
                    const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z);
                    graph.cameraPosition(
                        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                        node, 
                        1000
                    );
                } else {
                    graph.centerAt(node.x, node.y, 800);
                    graph.zoom(1.5, 800);
                }
            })
            .onNodeDragEnd(node => {
                node.fx = node.x;
                node.fy = node.y;
            })
            .onBackgroundClick(() => {
                detailsPanel.classList.add('hidden');
            });

        if (!is3D) {
            // Custom node rendering for glow and icons in 2D
            graph.nodeCanvasObject((node, ctx, globalScale) => {
                const label = node.label;
                const color = colors[label] || '#999';
                const size = 6;
                
                ctx.shadowBlur = 15 / globalScale;
                ctx.shadowColor = color;
                
                ctx.beginPath();
                ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                ctx.fillStyle = color;
                ctx.fill();
                
                ctx.shadowBlur = 0;
                
                if (globalScale > 1.2) {
                    const fontSize = 10 / globalScale;
                    ctx.font = `${fontSize}px Inter`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                    const title = node.properties.title || node.properties.path || node.id;
                    const truncated = title.length > 20 ? title.substring(0, 17) + '...' : title;
                    ctx.fillText(truncated, node.x, node.y + size + 2);
                }
            });
        } else {
            // Form a literal brain structure in 3D using custom physics
            graph.d3Force('charge').strength(-15); // Reduce repulsion
            graph.d3Force('brain_structure', (alpha) => {
                graphData.nodes.forEach((node, i) => {
                    // Split into Left and Right brain hemispheres
                    const isLeft = i % 2 === 0;
                    
                    // Centers of the two lobes
                    const cx = isLeft ? -40 : 40;
                    const cy = 0;
                    const cz = 0;
                    
                    const dx = node.x - cx;
                    const dy = node.y - cy;
                    const dz = node.z - cz;
                    
                    const distance = Math.sqrt(dx*dx + dy*dy + dz*dz) || 1;
                    const targetRadius = 60; // Size of the lobes
                    
                    // Pull nodes towards the surface of the lobe
                    const pull = (distance - targetRadius) * alpha * 0.1;
                    
                    node.vx -= (dx / distance) * pull;
                    // Compress vertically (brains are flatter on bottom/top)
                    node.vy -= (dy / distance) * pull * 1.5;
                    // Elongate front-to-back
                    node.vz -= (dz / distance) * pull * 0.7;
                });
            });
            
            // Give links an organic curve without crazy animations
            graph.linkCurvature(0.2);
        }
        
        graph.graphData(data);
        if (!is3D) {
            setTimeout(() => graph.zoomToFit(400), 500);
        }
    }

    // Fetch data
    async function fetchData() {
        try {
            const response = await fetch('/api/graph');
            const data = await response.json();
            graphData = data;
            initGraph(graphData);
        } catch (error) {
            console.error('Error fetching graph data:', error);
        }
    }

    fetchData();

    // Toggle 3D
    const toggle3dBtn = document.getElementById('toggle-3d');
    toggle3dBtn.addEventListener('click', () => {
        is3D = !is3D;
        initGraph(graphData);
        toggle3dBtn.querySelector('i').setAttribute('data-lucide', is3D ? 'layers' : 'box');
        lucide.createIcons();
    });

    // Reset view
    resetViewBtn.addEventListener('click', () => {
        if (is3D) {
            graph.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
        } else {
            graph.zoomToFit(600);
        }
    });

    // Search
    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        if (!term || term.length <= 2) return;

        const matches = graphData.nodes.filter(n => 
            (n.properties.title || n.properties.path || n.id).toLowerCase().includes(term)
        );

        if (matches.length > 0) {
            const first = matches[0];
            showNodeDetails(first);
            if (is3D) {
                const distance = 120;
                const distRatio = 1 + distance/Math.hypot(first.x, first.y, first.z);
                graph.cameraPosition(
                    { x: first.x * distRatio, y: first.y * distRatio, z: first.z * distRatio },
                    first,
                    1000
                );
            } else {
                graph.centerAt(first.x, first.y, 600);
                graph.zoom(1.5, 600);
            }
        }
    });

    function showNodeDetails(node) {
        const { label, properties } = node;
        
        const tag = document.getElementById('node-label-tag');
        tag.textContent = label;
        tag.style.color = colors[label];
        tag.style.backgroundColor = colors[label] + '22';
        tag.style.border = `1px solid ${colors[label]}44`;
        
        document.getElementById('node-title').textContent = properties.title || properties.path || properties.name || node.id;
        
        const propsContainer = document.getElementById('node-properties');
        propsContainer.innerHTML = '';
        
        // Show logical ID prominently at the top of properties
        const idDiv = document.createElement('div');
        idDiv.className = 'property';
        idDiv.innerHTML = `
            <span class="prop-label">ID</span>
            <span class="prop-value" style="font-family: monospace; font-size: 0.8rem; opacity: 0.8;">${node.id}</span>
        `;
        propsContainer.appendChild(idDiv);
        
        // System properties to hide from the general list
        const hideList = ['id', 'ID', 'title', 'name', '_label'];
        
        for (const [key, value] of Object.entries(properties)) {
            if (hideList.includes(key) || !value || value === 'null') continue;
            
            // Skip if it looks like a Kuzu internal ID object that we already stringified
            if (typeof value === 'string' && value.includes("'offset':") && value.includes("'table':")) continue;
            
            const propDiv = document.createElement('div');
            propDiv.className = 'property';
            
            // Handle potentially complex values
            const displayValue = typeof value === 'object' ? JSON.stringify(value) : value;
            
            propDiv.innerHTML = `
                <span class="prop-label">${key.replace(/_/g, ' ')}</span>
                <span class="prop-value">${displayValue}</span>
            `;
            propsContainer.appendChild(propDiv);
        }
        
        // Show linked nodes
        const linksContainer = document.getElementById('links-container');
        const linksList = document.getElementById('node-links');
        linksList.innerHTML = '';
        
        const nodeLinks = graphData.links.filter(l => 
            (typeof l.source === 'object' ? l.source.id === node.id : l.source === node.id) || 
            (typeof l.target === 'object' ? l.target.id === node.id : l.target === node.id)
        );
        
        if (nodeLinks.length > 0) {
            linksContainer.classList.remove('hidden');
            nodeLinks.forEach(link => {
                const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                
                const otherId = sourceId === node.id ? targetId : sourceId;
                const otherNode = graphData.nodes.find(n => n.id === otherId);
                
                if (otherNode) {
                    const linkDiv = document.createElement('div');
                    linkDiv.className = 'link-item';
                    const otherTitle = otherNode.properties.title || otherNode.properties.path || otherNode.id;
                    const truncatedTitle = otherTitle.length > 35 ? otherTitle.substring(0, 32) + '...' : otherTitle;
                    
                    linkDiv.innerHTML = `
                        <span class="dot" style="background-color: ${colors[otherNode.label]}"></span>
                        <div style="display: flex; flex-direction: column; gap: 2px;">
                            <span style="font-size: 0.7rem; color: var(--text-dim); font-weight: 700;">${link.type}</span>
                            <span class="link-label">${truncatedTitle}</span>
                        </div>
                    `;
                    linkDiv.onclick = (e) => {
                        e.stopPropagation();
                        showNodeDetails(otherNode);
                        graph.centerAt(otherNode.x, otherNode.y, 800);
                        graph.zoom(1.5, 800);
                    };
                    linksList.appendChild(linkDiv);
                }
            });
        } else {
            linksContainer.classList.add('hidden');
        }
        
        detailsPanel.classList.remove('hidden');
    }
});
