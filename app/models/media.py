from database_setup import Base
from sqlalchemy import Column, Integer, String, Enum, Text
class Media(Base):
    __tablename__ = 'media'

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_type = Column(Enum('ebook', 'audiobook'), nullable=False)
    file_url = Column(String(500), nullable=False)  # URL do pliku w Azure Blob Storage
    title = Column(String(250), nullable=False)
    author = Column(String(250), nullable=False)
    publish_year = Column(Integer, nullable=False)
    genre = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    cover_image_url = Column(String(500), nullable=True)