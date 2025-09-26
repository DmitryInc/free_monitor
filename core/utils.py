def delete_simillar_routes(routes: list):
    """
    Merge routes from different messages by regions with saving the latest message
    
    Args:
        routes: List of TelegramMessage objects
        
    Returns:
        String with merged routes by regions
    """
    region_messages = {}
    
    for message in routes:
        if not message.text:
            continue
            
        lines = message.text.strip().split('\n')
        current_region = None
        content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.endswith(':'):
                if current_region and content:
                    _save_region(region_messages, current_region, content, message.date)
                
                current_region = line
                content = []

            elif current_region:
                content.append(line)
        
        if current_region and content:
            _save_region(region_messages, current_region, content, message.date)
    
    result_lines = []
    for region in sorted(region_messages.keys()):
        result_lines.append(region)
        result_lines.extend(region_messages[region]['content'])
        result_lines.append("")
    
    return "\n".join(result_lines).strip()

def _save_region(region_messages, region, content, date):
    if region not in region_messages or date > region_messages[region]['date']:
        region_messages[region] = {'content': content.copy(), 'date': date}