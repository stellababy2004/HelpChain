from backend.helpchain_backend.src.app import create_app
from backend.models import db, ProfessionalLead

app=create_app()

with app.app_context():

    data = [
        ("Marie Dubois","marie.dubois@demo.fr","Assistante sociale","Boulogne-Billancourt"),
        ("Jean Martin","jean.martin@demo.fr","Psychologue","Boulogne-Billancourt"),
        ("Claire Bernard","claire.bernard@demo.fr","Juriste social","Boulogne-Billancourt"),
        ("Thomas Leroy","thomas.leroy@demo.fr","Insertion emploi","Boulogne-Billancourt"),
        ("Sophie Petit","sophie.petit@demo.fr","Logement urgence","Boulogne-Billancourt"),
        ("Nicolas Moreau","nicolas.moreau@demo.fr","Médiateur familial","Paris"),
        ("Julie Simon","julie.simon@demo.fr","Santé mentale","Paris")
    ]

    added = 0

    for full_name,email,speciality,city in data:
        exists = ProfessionalLead.query.filter_by(email=email).first()
        if not exists:
            p = ProfessionalLead(
                full_name=full_name,
                email=email,
                specialty=speciality,
                city=city,
                is_active=True
            )
            db.session.add(p)
            added += 1

    db.session.commit()

    print("Professionals added:", added)
    print("Total professionals:", ProfessionalLead.query.count())
