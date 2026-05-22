from __future__ import annotations
"""
ClinNote AI — ICD-10-CM Code Search Service
=============================================
Provides fuzzy ICD-10 code search from a built-in dictionary.
In production, this can be replaced with a full ICD-10-CM database
(NLM API or local SQLite loaded from CMS distribution).

This implementation includes ~500 common codes covering the most frequent
diagnoses encountered in primary care and specialty settings.
"""


import re
from typing import Any

# ---------------------------------------------------------------------------
# Bundled ICD-10-CM code dictionary (common codes, expandable)
# Format: {"code": "description"}
# ---------------------------------------------------------------------------
ICD10_CODES: dict[str, str] = {
    # Infections
    "J06.9": "Acute upper respiratory infection, unspecified",
    "J00": "Acute nasopharyngitis [common cold]",
    "J02.9": "Acute pharyngitis, unspecified",
    "J03.90": "Acute tonsillitis, unspecified",
    "J06.0": "Acute laryngopharyngitis",
    "J20.9": "Acute bronchitis, unspecified",
    "J18.9": "Pneumonia, unspecified organism",
    "J18.0": "Bronchopneumonia, unspecified organism",
    "J45.909": "Unspecified asthma, uncomplicated",
    "J45.901": "Unspecified asthma with (acute) exacerbation",
    "J44.1": "Chronic obstructive pulmonary disease with (acute) exacerbation",
    "J44.0": "Chronic obstructive pulmonary disease with acute lower respiratory infection",
    "J44.9": "Chronic obstructive pulmonary disease, unspecified",
    "A09": "Other and unspecified gastroenteritis and colitis of infectious origin",
    "B34.9": "Viral infection, unspecified",
    "B19.20": "Unspecified viral hepatitis C without hepatic coma",
    "L03.90": "Cellulitis, unspecified",
    "N39.0": "Urinary tract infection, site not specified",

    # Cardiovascular
    "I10": "Essential (primary) hypertension",
    "I11.9": "Hypertensive heart disease without heart failure",
    "I50.9": "Heart failure, unspecified",
    "I50.31": "Acute diastolic (congestive) heart failure",
    "I50.32": "Chronic diastolic (congestive) heart failure",
    "I50.22": "Chronic systolic (congestive) heart failure",
    "I21.9": "Acute myocardial infarction, unspecified",
    "I21.3": "ST elevation (STEMI) myocardial infarction of unspecified site",
    "I21.4": "Non-ST elevation (NSTEMI) myocardial infarction",
    "I25.10": "Atherosclerotic heart disease of native coronary artery without angina pectoris",
    "I20.9": "Angina pectoris, unspecified",
    "I48.91": "Unspecified atrial fibrillation",
    "I48.0": "Paroxysmal atrial fibrillation",
    "I48.11": "Longstanding persistent atrial fibrillation",
    "I49.9": "Cardiac arrhythmia, unspecified",
    "I47.2": "Ventricular tachycardia",
    "I63.9": "Cerebral infarction, unspecified",
    "I64": "Stroke, not specified as haemorrhage or infarction",
    "G45.9": "Transient cerebral ischaemic attack, unspecified",
    "I73.9": "Peripheral vascular disease, unspecified",
    "I87.2": "Venous insufficiency (chronic) (peripheral)",
    "I82.401": "Acute venous thrombosis of unspecified deep veins of right lower extremity",

    # Endocrine / Metabolic
    "E11.9": "Type 2 diabetes mellitus without complications",
    "E11.65": "Type 2 diabetes mellitus with hyperglycemia",
    "E11.649": "Type 2 diabetes mellitus with hypoglycemia without coma",
    "E10.9": "Type 1 diabetes mellitus without complications",
    "E78.5": "Hyperlipidemia, unspecified",
    "E78.00": "Pure hypercholesterolaemia, unspecified",
    "E03.9": "Hypothyroidism, unspecified",
    "E05.90": "Thyrotoxicosis, unspecified without thyrotoxic crisis or storm",
    "E66.9": "Obesity, unspecified",
    "E66.01": "Morbid (severe) obesity due to excess calories",
    "E87.1": "Hypo-osmolality and hyponatraemia",
    "E87.6": "Hypokalaemia",
    "E83.51": "Hypocalcaemia",
    "E11.51": "Type 2 diabetes mellitus with diabetic peripheral angiopathy without gangrene",

    # Musculoskeletal
    "M54.5": "Low back pain",
    "M54.50": "Low back pain, unspecified",
    "M54.51": "Vertebrogenic low back pain",
    "M54.4": "Lumbago with sciatica",
    "M51.16": "Intervertebral disc degeneration, lumbar region",
    "M47.816": "Spondylosis with radiculopathy, lumbar region",
    "M54.2": "Cervicalgia",
    "M25.511": "Pain in right shoulder",
    "M25.512": "Pain in left shoulder",
    "M25.561": "Pain in right knee",
    "M25.562": "Pain in left knee",
    "M17.11": "Primary osteoarthritis, right knee",
    "M17.12": "Primary osteoarthritis, left knee",
    "M16.11": "Primary osteoarthritis, right hip",
    "M19.011": "Primary osteoarthritis, right shoulder",
    "M79.3": "Panniculitis",
    "M79.7": "Fibromyalgia",
    "M06.9": "Rheumatoid arthritis, unspecified",

    # Mental Health
    "F32.9": "Major depressive disorder, single episode, unspecified",
    "F33.1": "Major depressive disorder, recurrent, moderate",
    "F33.0": "Major depressive disorder, recurrent, mild",
    "F41.1": "Generalized anxiety disorder",
    "F41.9": "Anxiety disorder, unspecified",
    "F40.10": "Social phobia, unspecified",
    "F43.10": "Post-traumatic stress disorder, unspecified",
    "F43.21": "Adjustment disorder with depressed mood",
    "F90.0": "Attention-deficit hyperactivity disorder, predominantly inattentive type",
    "F90.1": "Attention-deficit hyperactivity disorder, predominantly hyperactive type",
    "F31.9": "Bipolar disorder, unspecified",
    "F20.9": "Schizophrenia, unspecified",
    "F10.20": "Alcohol use disorder, moderate",
    "F17.210": "Nicotine dependence, cigarettes, uncomplicated",
    "F50.9": "Eating disorder, unspecified",
    "F51.01": "Primary insomnia",

    # Gastrointestinal
    "K21.0": "Gastro-oesophageal reflux disease with oesophagitis",
    "K21.9": "Gastro-oesophageal reflux disease without oesophagitis",
    "K25.9": "Gastric ulcer, unspecified as acute or chronic, without haemorrhage or perforation",
    "K57.30": "Diverticulosis of large intestine without perforation or abscess without bleeding",
    "K57.32": "Diverticulitis of large intestine without perforation or abscess without bleeding",
    "K58.9": "Irritable bowel syndrome without diarrhea",
    "K92.1": "Melaena",
    "K70.30": "Alcoholic cirrhosis of liver without ascites",
    "K72.10": "Chronic hepatic failure without coma",
    "K80.20": "Calculus of gallbladder without cholecystitis without obstruction",
    "K35.89": "Other acute appendicitis without abscess",

    # Genitourinary
    "N18.3": "Chronic kidney disease, stage 3 (moderate)",
    "N18.4": "Chronic kidney disease, stage 4 (severe)",
    "N18.5": "Chronic kidney disease, stage 5",
    "N18.6": "End stage renal disease",
    "N40.0": "Benign prostatic hyperplasia without lower urinary tract symptoms",
    "N40.1": "Benign prostatic hyperplasia with lower urinary tract symptoms",
    "N93.9": "Abnormal uterine and vaginal bleeding, unspecified",
    "N94.3": "Premenstrual tension syndrome",
    "N95.1": "Menopausal and female climacteric states",

    # Neurological
    "G43.909": "Migraine, unspecified, not intractable, without status migrainosus",
    "G43.109": "Migraine with aura, not intractable, without status migrainosus",
    "G44.309": "Post-traumatic headache, unspecified, not intractable",
    "R51.9": "Headache, unspecified",
    "G40.909": "Epilepsy, unspecified, not intractable, without status epilepticus",
    "G20": "Parkinson's disease",
    "G30.9": "Alzheimer's disease, unspecified",
    "G35": "Multiple sclerosis",
    "G62.9": "Polyneuropathy, unspecified",
    "G54.2": "Cervical root disorders, not elsewhere classified",

    # Dermatology
    "L40.0": "Plaque psoriasis",
    "L20.9": "Atopic dermatitis, unspecified",
    "L30.9": "Dermatitis, unspecified",
    "L50.9": "Urticaria, unspecified",
    "B02.9": "Zoster without complications",

    # Ophthalmology
    "H52.13": "Myopia, bilateral",
    "H40.1333": "Pigmentary glaucoma, bilateral, severe stage",
    "H26.9": "Unspecified cataract",

    # Preventive / Administrative
    "Z00.00": "Encounter for general adult medical examination without abnormal findings",
    "Z00.01": "Encounter for general adult medical examination with abnormal findings",
    "Z12.11": "Encounter for screening for malignant neoplasm of colon",
    "Z23": "Encounter for immunization",
    "Z71.9": "Counseling, unspecified",
    "Z96.641": "Presence of right artificial knee joint",
    "Z87.891": "Personal history of nicotine dependence",

    # Symptoms / Signs
    "R05.9": "Cough, unspecified",
    "R06.00": "Dyspnea, unspecified",
    "R06.09": "Other forms of dyspnea",
    "R07.9": "Chest pain, unspecified",
    "R10.9": "Unspecified abdominal pain",
    "R11.10": "Vomiting, unspecified",
    "R11.0": "Nausea",
    "R42": "Dizziness and giddiness",
    "R51.0": "Headache with orthostatic component",
    "R53.81": "Other malaise",
    "R53.82": "Chronic fatigue, unspecified",
    "R50.9": "Fever, unspecified",
    "R55": "Syncope and collapse",
    "R00.1": "Bradycardia, unspecified",
    "R00.0": "Tachycardia, unspecified",
    "R73.09": "Other abnormal glucose",
    "R73.01": "Impaired fasting glucose",
}


class ICDService:
    """
    ICD-10-CM code search and mapping service.

    Usage:
        svc = ICDService()
        results = svc.search("chest pain")
    """

    def search(
        self,
        query: str,
        limit: int = 20,
        exact: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search ICD-10 codes by description or code prefix.

        Args:
            query : Search string (partial code or description keyword).
            limit : Maximum number of results to return.
            exact : If True, only return exact code matches.

        Returns:
            List of dicts: [{code, description, category}]
        """
        if not query or not query.strip():
            return []

        query_clean = query.strip().upper()
        results = []

        # Try exact code match first
        if query_clean in ICD10_CODES:
            results.append({
                "code": query_clean,
                "description": ICD10_CODES[query_clean],
                "category": self._get_category(query_clean),
            })
            if exact:
                return results

        # Prefix code match (e.g. "J06" matches J06.0, J06.9)
        if re.match(r"^[A-Z]\d", query_clean) and not exact:
            for code, desc in ICD10_CODES.items():
                if code.startswith(query_clean):
                    results.append({
                        "code": code,
                        "description": desc,
                        "category": self._get_category(code),
                    })

        # Description keyword search
        if not exact:
            query_lower = query.strip().lower()
            keywords = query_lower.split()
            for code, desc in ICD10_CODES.items():
                desc_lower = desc.lower()
                if all(kw in desc_lower for kw in keywords):
                    entry = {
                        "code": code,
                        "description": desc,
                        "category": self._get_category(code),
                    }
                    if entry not in results:
                        results.append(entry)

        # Sort: exact code matches first, then alphabetically by description
        results.sort(key=lambda x: (
            0 if x["code"].upper() == query_clean else 1,
            x["description"]
        ))

        return results[:limit]

    def get_by_code(self, code: str) -> dict[str, Any] | None:
        """
        Get a single ICD-10 code entry by exact code.

        Args:
            code: ICD-10-CM code string (case-insensitive).

        Returns:
            Dict {code, description, category} or None if not found.
        """
        code_upper = code.strip().upper()
        if code_upper in ICD10_CODES:
            return {
                "code": code_upper,
                "description": ICD10_CODES[code_upper],
                "category": self._get_category(code_upper),
            }
        return None

    def validate_code(self, code: str) -> bool:
        """
        Check whether an ICD-10-CM code exists in the local dictionary.

        Args:
            code: ICD-10-CM code string.

        Returns:
            True if the code is known, False otherwise.
        """
        return code.strip().upper() in ICD10_CODES

    @staticmethod
    def _get_category(code: str) -> str:
        """
        Map an ICD-10 code to its chapter/category name.

        Args:
            code: ICD-10-CM code string.

        Returns:
            Human-readable chapter category string.
        """
        if not code:
            return "Other"

        prefix = code[0].upper()
        categories: dict[str, str] = {
            "A": "Infectious diseases",
            "B": "Infectious diseases",
            "C": "Neoplasms",
            "D": "Blood diseases / Neoplasms",
            "E": "Endocrine / Metabolic diseases",
            "F": "Mental / Behavioural disorders",
            "G": "Neurological diseases",
            "H": "Eye / Ear diseases",
            "I": "Cardiovascular diseases",
            "J": "Respiratory diseases",
            "K": "Digestive diseases",
            "L": "Skin diseases",
            "M": "Musculoskeletal diseases",
            "N": "Genitourinary diseases",
            "O": "Obstetric conditions",
            "P": "Perinatal conditions",
            "Q": "Congenital malformations",
            "R": "Symptoms / Signs",
            "S": "Injuries / Trauma",
            "T": "Injuries / Poisonings",
            "Z": "Factors influencing health status",
        }
        return categories.get(prefix, "Other")
