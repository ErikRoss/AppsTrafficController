from flask_table import Table, Col


class AppsTable(Table):
    classes = ['table', 'table-striped', 'table-bordered', 'table-hover']
    id = Col('Id', show=False)
    title = Col('Title')
    url = Col('URL')
    image = Col('Image')
    operating_system = Col('Operating System')
    tags = Col('Tags')
    unique_tag = Col('Unique Tag')
    description = Col('Description')
    status = Col('Status')
    
    no_items = 'No Apps Found'
    

class CampaignsTable(Table):
    classes = ['table', 'table-striped', 'table-bordered', 'table-hover']
    id = Col('Id', show=False)
    title = Col('Title')
    description = Col('Description')
    geo = Col('Geo')
    apps = Col('Apps')
    custom_parameters = Col('Custom Parameters')
    hash_code = Col('Hash Code')
    
    no_items = 'No Campaigns Found'
