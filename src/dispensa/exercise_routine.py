from pydantic import BaseModel, ConfigDict

_PROGRESSIVE_NOTE = (
    "Ordine dal più facile al più difficile - non farli tutti dal giorno 1, "
    "avanza gradualmente."
)


class RoutineExercise(BaseModel):
    """One back exercise in the routine, keyed by a stable id."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    pose: str
    reps: str
    tip: str


class RoutineCategory(BaseModel):
    """A group of exercises; name matches an ExerciseCategory value."""

    model_config = ConfigDict(frozen=True)

    name: str
    color: str
    tint: str
    note: str | None
    exercises: tuple[RoutineExercise, ...]


# The routine is the single source of truth for exercise identity. The log stores
# the id, so renaming an exercise here keeps its history attached. The frontend
# fetches this (presentation included) instead of hardcoding it.
ROUTINE: tuple[RoutineCategory, ...] = (
    RoutineCategory(
        name="Mobilize",
        color="#7C9885",
        tint="#f2f6f3",
        note=None,
        exercises=(
            RoutineExercise(
                id="pelvic-lift",
                name="Pelvic Lift",
                pose="supineBent",
                reps="10 volte",
                tip=(
                    "Muovi il bacino avanti e indietro appiattendo e inarcando "
                    "leggermente la zona lombare. Movimento piccolo e lento, non "
                    "forzare."
                ),
            ),
            RoutineExercise(
                id="knee-rolling",
                name="Knee Rolling",
                pose="supineBent",
                reps="10 volte",
                tip=(
                    "Ginocchia unite, ruota entrambe da un lato senza sollevare le "
                    "spalle da terra. Ferma se senti tirare troppo."
                ),
            ),
            RoutineExercise(
                id="hip-flex",
                name="Hip Flex",
                pose="supineTabletop",
                reps="10 volte per lato",
                tip=(
                    "Porta un ginocchio verso il petto tenendo l'altra gamba rilassata. "
                    "Non trattenere il respiro."
                ),
            ),
            RoutineExercise(
                id="knees-to-chest",
                name="Knees to Chest",
                pose="supineTabletop",
                reps="10 volte",
                tip=(
                    "Entrambe le ginocchia al petto insieme, dondolo leggero se comodo. "
                    "Fermati se senti fitte, non solo tensione."
                ),
            ),
            RoutineExercise(
                id="sitting-forward-position",
                name="Sitting Forward Position",
                pose="seatedForward",
                reps="10 volte",
                tip=(
                    "Seduta su sedia, piega il busto in avanti portando le mani verso "
                    "il pavimento. Piega dalle anche, non incurvare solo le spalle."
                ),
            ),
            RoutineExercise(
                id="hip-extension",
                name="Hip Extension",
                pose="standingLegBack",
                reps="10 volte per lato",
                tip=(
                    "In piedi, porta una gamba dritta indietro senza inarcare la zona "
                    "lombare. Il movimento parte dall'anca, non dalla schiena."
                ),
            ),
            RoutineExercise(
                id="forward-bend",
                name="Forward Bend",
                pose="standingForwardFold",
                reps="10 volte",
                tip=(
                    "Scendi lentamente vertebra per vertebra, ginocchia morbide. "
                    "Risali altrettanto lentamente, testa per ultima."
                ),
            ),
            RoutineExercise(
                id="front-lying-back-lift",
                name="Front Lying Back Lift",
                pose="proneExtend",
                reps="10 volte",
                tip=(
                    "A pancia in giù, solleva leggermente il petto senza spingere con "
                    "le mani. Sollevamento piccolo, non da superman completo."
                ),
            ),
        ),
    ),
    RoutineCategory(
        name="Move",
        color="#6B8CAE",
        tint="#f0f4f8",
        note=None,
        exercises=(
            RoutineExercise(
                id="cat-camel",
                name="Cat / Camel",
                pose="quadruped",
                reps="10 volte",
                tip=(
                    "Carponi, alterna inarcare (camel) e incavare (cat) la schiena "
                    "seguendo il respiro. Movimento fluido, non a scatti."
                ),
            ),
            RoutineExercise(
                id="childs-pose",
                name="Child's Pose",
                pose="childPose",
                reps="10 volte",
                tip=(
                    "Siedi sui talloni, busto disteso in avanti, braccia lunghe "
                    "davanti. Lascia che il peso affondi, non spingere."
                ),
            ),
            RoutineExercise(
                id="thread-the-needle",
                name="Thread the Needle",
                pose="quadruped",
                reps="10 volte per lato",
                tip=(
                    "Carponi, infila un braccio sotto l'altra spalla ruotando il busto. "
                    "Muovi dal centro schiena, tieni i fianchi fermi."
                ),
            ),
            RoutineExercise(
                id="leg-cross-overs",
                name="Leg Cross Overs",
                pose="sideLying",
                reps="5 volte",
                tip=(
                    "Da sdraiata, porta le ginocchia piegate da un lato all'altro "
                    "tenendo le spalle a terra. Rotazione controllata, non lasciarla "
                    "cadere di peso."
                ),
            ),
            RoutineExercise(
                id="marching",
                name="Marching",
                pose="standingKneeUp",
                reps="10 volte per lato",
                tip=(
                    "In piedi o sdraiata, solleva un ginocchio alla volta come se "
                    "marciassi. Bacino stabile, non oscillare."
                ),
            ),
            RoutineExercise(
                id="hip-up-and-out",
                name="Hip Up and Out",
                pose="standingKneeUp",
                reps="4-5 volte, entrambi i lati",
                tip=(
                    "Solleva il ginocchio poi apri l'anca verso l'esterno. Movimento "
                    "lento, appoggio stabile sull'altra gamba."
                ),
            ),
            RoutineExercise(
                id="shoulder-blade-squeeze",
                name="Shoulder Blade Squeeze",
                pose="standingSqueeze",
                reps="10 volte",
                tip=(
                    "Stringi le scapole verso la colonna, spalle basse e rilassate. "
                    "Non alzare le spalle verso le orecchie."
                ),
            ),
            RoutineExercise(
                id="standing-bow-and-arrow",
                name="Standing Bow and Arrow",
                pose="standingLegBack",
                reps="10 volte per lato",
                tip=(
                    "In piedi, simula il gesto di tirare con l'arco ruotando il busto. "
                    "Ruota dal torace, mantieni il bacino stabile."
                ),
            ),
        ),
    ),
    RoutineCategory(
        name="Strengthen",
        color="#B08968",
        tint="#f9f3ee",
        note=_PROGRESSIVE_NOTE,
        exercises=(
            RoutineExercise(
                id="static-glutes",
                name="Static Glutes",
                pose="supineBent",
                reps="10 volte, tieni 5 sec",
                tip=(
                    "Sdraiata, ginocchia piegate, contrai i glutei senza sollevare il "
                    "bacino. Solo contrazione isometrica, nessun movimento."
                ),
            ),
            RoutineExercise(
                id="bilateral-bridge",
                name="Bilateral Bridge",
                pose="supineBent",
                reps="10 volte",
                tip=(
                    "Solleva il bacino da terra fino ad allineare "
                    "ginocchia-anche-spalle. Non inarcare oltre la linea retta, "
                    "spingi con i talloni."
                ),
            ),
            RoutineExercise(
                id="offset-bridge",
                name="Offset Bridge",
                pose="supineBent",
                reps="10 volte per lato",
                tip=(
                    "Come il ponte, ma con più peso su una gamba. Bacino "
                    "livellato, non far cadere il lato scarico."
                ),
            ),
            RoutineExercise(
                id="split-stance-hip-hinge",
                name="Split Stance Hip Hinge",
                pose="lungeSquat",
                reps="10 volte per lato",
                tip=(
                    "Un piede avanti, uno indietro, piega dalle anche mantenendo la "
                    "schiena dritta. La schiena resta neutra, il movimento è all'anca."
                ),
            ),
            RoutineExercise(
                id="forward-bend-hip-hinge",
                name="Forward Bend Hip Hinge",
                pose="standingForwardFold",
                reps="10 volte",
                tip=(
                    "Piega il busto in avanti spingendo i fianchi indietro, schiena "
                    "piatta, non arrotondata. Ginocchia morbide, peso sui talloni."
                ),
            ),
            RoutineExercise(
                id="squat",
                name="Squat",
                pose="lungeSquat",
                reps="10 volte",
                tip=(
                    "Scendi come per sederti su una sedia, ginocchia in linea con le "
                    "punte dei piedi. Non lasciare che le ginocchia cadano verso "
                    "l'interno."
                ),
            ),
            RoutineExercise(
                id="jefferson-curl",
                name="Jefferson Curl",
                pose="standingForwardFold",
                reps="8-10 volte, lento",
                tip=(
                    "Arrotola la colonna vertebra per vertebra dall'alto verso il "
                    "basso, poi risali allo stesso modo. Corpo libero, mai a "
                    "scatti. Evita se "
                    "hai un'ernia diagnosticata o dolore acuto in flessione - verifica "
                    "con il fisioterapista prima."
                ),
            ),
            RoutineExercise(
                id="exercise-top-end",
                name="Exercise Top End",
                pose="standingSqueeze",
                reps="10 volte",
                tip=(
                    "Solleva le braccia mantenendo il core attivo e la schiena neutra. "
                    "Non inarcare la lombare per guadagnare altezza."
                ),
            ),
        ),
    ),
    RoutineCategory(
        name="Activate",
        color="#A0616A",
        tint="#faf1f1",
        note=_PROGRESSIVE_NOTE,
        exercises=(
            RoutineExercise(
                id="superman",
                name="Superman",
                pose="proneExtend",
                reps="10 volte",
                tip=(
                    "A pancia in giù, solleva braccio e gamba opposti insieme. "
                    "Sollevamento controllato, non un colpo secco verso l'alto."
                ),
            ),
            RoutineExercise(
                id="deadbug",
                name="Deadbug",
                pose="supineTabletop",
                reps="10 volte per lato",
                tip=(
                    "Sdraiata, ginocchia a 90°, estendi braccio e gamba opposti "
                    "mantenendo la lombare a contatto col pavimento. Se la schiena si "
                    "inarca, riduci l'ampiezza del movimento."
                ),
            ),
            RoutineExercise(
                id="half-front-plank",
                name="Half Front Plank",
                pose="plank",
                reps="tieni 10-15 sec",
                tip=(
                    "Sugli avambracci, corpo in linea da testa a ginocchia. Non far "
                    "cadere il bacino né alzarlo a punta."
                ),
            ),
            RoutineExercise(
                id="half-side-plank",
                name="Half Side Plank",
                pose="sideLying",
                reps="tieni 10-15 sec per lato",
                tip=(
                    "Su un fianco, appoggio su avambraccio e ginocchio, solleva il "
                    "bacino. Corpo in linea, non ruotare in avanti."
                ),
            ),
            RoutineExercise(
                id="childs-pose-extension",
                name="Child's Pose + Extension",
                pose="childPose",
                reps="10 volte",
                tip=(
                    "Dalla posizione del bambino, scivola in avanti allungando la "
                    "schiena, poi torna indietro. Movimento lento e continuo."
                ),
            ),
            RoutineExercise(
                id="lunge-and-twist",
                name="Lunge and Twist",
                pose="lungeSquat",
                reps="10 volte per lato",
                tip=(
                    "In affondo, ruota il busto verso la gamba avanti. Ruota dal torace "
                    "tenendo il bacino rivolto in avanti."
                ),
            ),
        ),
    ),
)


def name_to_id() -> dict[str, str]:
    """Map each exercise's current display name to its stable id (backfill use)."""
    return {
        exercise.name: exercise.id
        for category in ROUTINE
        for exercise in category.exercises
    }


def all_ids() -> frozenset[str]:
    """Return every known exercise id."""
    return frozenset(
        exercise.id for category in ROUTINE for exercise in category.exercises
    )
