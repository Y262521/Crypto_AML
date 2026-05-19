#!/usr/bin/env python3
"""
Generate a comprehensive PDF document explaining AML system components
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from datetime import datetime

def create_pdf():
    """Create the AML system documentation PDF"""
    
    # Create PDF
    pdf_path = "/home/hakim/Crypto_AML/AML_System_Documentation.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=12
    )
    
    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontSize=9.5,
        leftIndent=20,
        spaceAfter=4,
        leading=11
    )
    
    story = []
    
    # Title Page
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Crypto AML System", title_style))
    story.append(Paragraph("Component Explanations", styles['Heading2']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(PageBreak())
    
    # Table of Contents
    story.append(Paragraph("Table of Contents", heading_style))
    story.append(Spacer(1, 0.1*inch))
    toc_items = [
        "1. Transaction Table",
        "2. Wallet Clustering",
        "3. Placement Detection",
        "4. Layering Detection",
        "5. Integration Detection",
        "6. System Architecture"
    ]
    for item in toc_items:
        story.append(Paragraph(item, bullet_style))
    story.append(PageBreak())
    
    # ==================== TRANSACTION TABLE ====================
    story.append(Paragraph("1. Transaction Table", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>What it is:</b>", subheading_style))
    story.append(Paragraph(
        "The Transaction Table is the foundation of the entire AML system. It stores all blockchain transactions extracted from Ethereum blocks, "
        "creating a normalized database of transaction data that serves as the source of truth for all downstream analysis.",
        body_style
    ))
    
    story.append(Paragraph("<b>Key Fields:</b>", subheading_style))
    tx_fields = [
        "Transaction Hash (unique identifier)",
        "Sender & Recipient Addresses",
        "Value in ETH",
        "Timestamp & Block Number",
        "Gas Used & Transaction Status"
    ]
    for field in tx_fields:
        story.append(Paragraph(field, bullet_style))
    
    story.append(Paragraph("<b>Why It's Here:</b>", subheading_style))
    story.append(Paragraph(
        "Without normalized transaction data, you cannot perform any analysis. This table enables wallet clustering, pattern detection, "
        "and tracing of illicit fund flows across the blockchain.",
        body_style
    ))
    
    story.append(Paragraph("<b>Database Structure:</b>", subheading_style))
    story.append(Paragraph(
        "Stored in MariaDB with indices on sender/recipient addresses and timestamps for efficient querying. "
        "Linked to wallet_clusters for quick lookup of which transactions belong to known clusters.",
        body_style
    ))
    
    story.append(Spacer(1, 0.15*inch))
    
    # ==================== WALLET CLUSTERING ====================
    story.append(Paragraph("2. Wallet Clustering", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>What it is:</b>", subheading_style))
    story.append(Paragraph(
        "Wallet Clustering identifies groups of blockchain addresses that are likely controlled by the same entity. "
        "This is crucial because criminals use multiple wallets to obscure ownership, and clustering reveals their true operational scope.",
        body_style
    ))
    
    story.append(Paragraph("<b>Algorithms (9 Heuristics):</b>", subheading_style))
    algorithms = [
        "<b>Deposit Reuse:</b> Identifies relay addresses used by multiple sources sending to the same collector",
        "<b>Coordinated Cashout:</b> Detects similar-sized withdrawals to the same exchange address from multiple wallets",
        "<b>Common Funder:</b> Finds wallets sharing both funding sources AND operational sinks",
        "<b>Behavioral Similarity:</b> Clusters wallets with 3+ shared transaction counterparties",
        "<b>Contract Interaction:</b> Groups wallets interacting with the same smart contracts",
        "<b>Token Flow:</b> Links addresses participating in the same token flows",
        "<b>Temporal Patterns:</b> Clusters wallets with synchronized transaction timing",
        "<b>Fan Pattern:</b> Detects hub-and-spoke structures (one hub distributing to many spokes)",
        "<b>Loop Detection:</b> Identifies circular transaction patterns suggesting coordinated control"
    ]
    for algo in algorithms:
        story.append(Paragraph(algo, bullet_style))
    
    story.append(Paragraph("<b>How It Works:</b>", subheading_style))
    story.append(Paragraph(
        "The system applies each heuristic to find address pairs that likely belong together. A Union-Find data structure merges detected "
        "relationships into clusters. For example, if heuristic A links addresses 1→2 and heuristic B links 2→3, all three are merged into one cluster.",
        body_style
    ))
    
    story.append(Paragraph("<b>Why It's Important:</b>", subheading_style))
    story.append(Paragraph(
        "AML regulators need to understand the full scope of a suspect's operation, not just individual addresses. "
        "Clustering reveals hidden connections and enables better risk assessment.",
        body_style
    ))
    
    story.append(Spacer(1, 0.15*inch))
    
    # ==================== PLACEMENT ====================
    story.append(Paragraph("3. Placement Detection", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>What it is:</b>", subheading_style))
    story.append(Paragraph(
        "Placement is the first stage of money laundering in the AML framework. It detects when illicit funds enter the financial system. "
        "On blockchain, this typically means cryptocurrency purchases or initial fund movements from illicit sources.",
        body_style
    ))
    
    story.append(Paragraph("<b>Detection Patterns:</b>", subheading_style))
    placement_patterns = [
        "<b>Structuring:</b> Multiple small, similar-sized deposits over time (low variance, consistent timing)",
        "<b>Smurfing:</b> Many unique young wallets sending small amounts to the same collector wallet",
        "<b>Micro-Funding:</b> Accumulated small payments (≥6 transactions, ≥0.4 ETH total, from diverse sources)"
    ]
    for pattern in placement_patterns:
        story.append(Paragraph(pattern, bullet_style))
    
    story.append(Paragraph("<b>Scoring Method:</b>", subheading_style))
    story.append(Paragraph(
        "Each detected pattern contributes a confidence score. The system also traces back to funding origins and links to wallet clusters "
        "to enhance existing cluster detection. Final score indicates probability of illicit fund entry.",
        body_style
    ))
    
    story.append(Paragraph("<b>Why It Matters:</b>", subheading_style))
    story.append(Paragraph(
        "Detecting placement early enables intervention at the critical first step of money laundering. "
        "Once funds are in the system, they become harder to track.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ==================== LAYERING ====================
    story.append(Paragraph("4. Layering Detection", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>What it is:</b>", subheading_style))
    story.append(Paragraph(
        "Layering is the second AML stage where criminals obscure fund origins through complex transactions. "
        "The system detects attempts to hide value flows and break transaction chains.",
        body_style
    ))
    
    story.append(Paragraph("<b>Detection Methods:</b>", subheading_style))
    layering_methods = [
        "<b>Peeling Chain:</b> Main transaction stream continues 3-5+ hops while small amounts 'shaved off' at each step to break patterns",
        "<b>Mixing Interaction:</b> Detects use of known mixers/anonymity tools (e.g., Tornado Cash)",
        "<b>Bridge Hopping:</b> Cross-chain transfers via bridges where amount varies ±3% with latency checks",
        "<b>Shell Wallets:</b> Identifies tightly-knit wallet networks with >70% internal transaction activity",
        "<b>High-Depth Chaining:</b> Long sequential chains where each transfers ≥70% of received value"
    ]
    for method in layering_methods:
        story.append(Paragraph(method, bullet_style))
    
    story.append(Paragraph("<b>How It Works:</b>", subheading_style))
    story.append(Paragraph(
        "The system traces transaction flows forward and backward, looking for patterns that indicate deliberate obfuscation. "
        "For example, a peeling chain has predictable fragmentation where the main wallet keeps most funds while creating many small decoys.",
        body_style
    ))
    
    story.append(Paragraph("<b>Why It's Critical:</b>", subheading_style))
    story.append(Paragraph(
        "Layering is where launderers do most of their work to hide connections. Detecting these patterns is essential for disrupting the entire operation.",
        body_style
    ))
    
    story.append(Spacer(1, 0.15*inch))
    
    # ==================== INTEGRATION ====================
    story.append(Paragraph("5. Integration Detection", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>What it is:</b>", subheading_style))
    story.append(Paragraph(
        "Integration is the final AML stage where laundered funds re-enter the legitimate financial system. "
        "The system detects when illicit funds attempt to be withdrawn or converted to real-world value.",
        body_style
    ))
    
    story.append(Paragraph("<b>Integration Indicators:</b>", subheading_style))
    integration_indicators = [
        "<b>Convergence:</b> Multiple sources funnel into a single collector wallet (≥5 senders converging)",
        "<b>Dormancy-to-Activation:</b> Long-idle wallets suddenly wake up and move ≥1 ETH (>30 days inactive before)",
        "<b>Exit Detection:</b> Direct transfers to known exchange addresses or real-world off-ramps",
        "<b>Reaggregation:</b> Fragments from layering stage recombined (≥4 inputs consolidating)",
        "<b>Final Confidence Scoring:</b> 30% placement + 35% layering + 35% integration = final risk score"
    ]
    for indicator in integration_indicators:
        story.append(Paragraph(indicator, bullet_style))
    
    story.append(Paragraph("<b>How It Works:</b>", subheading_style))
    story.append(Paragraph(
        "The system looks for suspicious patterns of fund consolidation and withdrawal. When multiple fragmented transactions suddenly "
        "converge before being sent to an exchange, it's a strong signal of integration.",
        body_style
    ))
    
    story.append(Paragraph("<b>Why It's Important:</b>", subheading_style))
    story.append(Paragraph(
        "Integration signals are actionable. Exchanges can freeze accounts, and law enforcement can intercept before funds fully re-enter the system.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ==================== SYSTEM ARCHITECTURE ====================
    story.append(Paragraph("6. System Architecture & Integration", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    story.append(Paragraph("<b>Frontend Components:</b>", subheading_style))
    frontend_items = [
        "<b>React Analysis Pages:</b> Dedicated pages for Placement, Layering, and Integration analysis with 'Analyze' buttons",
        "<b>Entity Intelligence Dashboard:</b> Right-panel showing address/cluster details, risk scores, and transaction history",
        "<b>Market Value Analysis:</b> Portfolio visualization with pie charts, holdings tables, and price history from CoinGecko",
        "<b>Navigation:</b> Unified menu system connecting all analysis views"
    ]
    for item in frontend_items:
        story.append(Paragraph(item, bullet_style))
    
    story.append(Paragraph("<b>Backend Systems:</b>", subheading_style))
    backend_items = [
        "<b>FastAPI Server:</b> REST API endpoints for cluster data, address balances, and risk scores",
        "<b>Async Scheduler:</b> Background jobs for continuous transaction ingestion and analysis updates",
        "<b>Balance Aggregator:</b> Fetches live ETH/ERC20 balances from Ethereum RPC nodes + CoinGecko prices",
        "<b>Multi-Database Support:</b> MongoDB (raw data), Neo4j (graph relationships), MariaDB (normalized analysis)"
    ]
    for item in backend_items:
        story.append(Paragraph(item, bullet_style))
    
    story.append(Paragraph("<b>Data Flow:</b>", subheading_style))
    story.append(Paragraph(
        "1) Blockchain data → Transaction Table (MariaDB) 2) Wallet Clustering algorithms → Cluster identification "
        "3) Placement/Layering/Integration detection → Risk scoring 4) Frontend displays results + enables deep analysis",
        body_style
    ))
    
    story.append(Spacer(1, 0.2*inch))
    
    # ==================== CONCLUSION ====================
    story.append(Paragraph("Summary", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    summary_text = (
        "The Crypto AML system implements the classic three-stage money laundering framework (Placement → Layering → Integration) "
        "specifically for blockchain. By combining wallet clustering with pattern detection, the system identifies illicit fund flows "
        "with high confidence. The modular architecture allows regulators and investigators to examine the evidence at each stage, "
        "supporting informed decision-making and compliance reporting."
    )
    story.append(Paragraph(summary_text, body_style))
    
    # Build PDF
    doc.build(story)
    print(f"✅ PDF created successfully: {pdf_path}")
    return pdf_path

if __name__ == "__main__":
    create_pdf()
