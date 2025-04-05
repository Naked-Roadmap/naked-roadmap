import os
basedir = os.path.abspath(os.path.dirname(__file__))
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
        
    # ####################################
    #
    # CUSTOMIZATIONS
    # Use this section to set global variables to customize your
    # deployment of the Naked Roadmap.
    #
    # ####################################
    
    # Your team or company name
    company_name = "Sigil Health" 
    
    # If you want the roadmap to be public
    public = True
    