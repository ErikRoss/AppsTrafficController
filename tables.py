from flask_table import Table, Col


class AppsTable(Table):
    classes = ['table', 'table-striped', 'table-bordered', 'table-hover']
    id = Col('Id', show=False)
    title = Col('Title')
    url = Col('URL')
    image = Col('Image')
    operating_system = Col('Operating System')
    alias = Col('Alias Tag')
    unique_tag = Col('Unique Tag')
    description = Col('Description')
    status = Col('Status')
