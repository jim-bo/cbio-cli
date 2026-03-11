# Templates Directory

## Structure

```
templates/
  base.html                         # Global HTML shell (head, scripts, body wrapper)
                                    # Includes shared/header.html and shared/footer.html

  shared/                           # Partials used across ALL pages
    header.html                     # Global nav bar (logo, nav links, Login button)
    footer.html                     # Global footer

  home/                             # Homepage (/)
    page.html                       # Full page template — extends base.html
    partials/
      subheader.html                # Query / Quick Search tab bar shell
      study_selector_header.html    # Study filter UI (search box, data type dropdown,
                                    # cancer type list + study list layout)
      study_selector_footer.html    # "Query By Gene / Explore Selected Studies" buttons
      cancer_type_list.html         # Left sidebar: organ system radio list
                                    # HTMX: posts to /studies on change
      cancer_study_list.html        # Right panel: grouped study list
                                    # HTMX swap target: #study-list-wrapper
      right_sidebar.html            # What's New, Example Queries, Testimonials

  study_view/                       # Study View (/study/summary?id=...)
    page.html                       # Full page template — extends base.html
    partials/
      study_header.html             # Study title, description, gene query box
      tab_bar.html                  # Summary | Clinical Data | CN Segments | Plots tabs
      cohort_controls.html          # Selection counter + Custom Selection/Charts/Groups buttons
      filter_bar.html               # Active filter pill tags + Clear All
      summary_tab.html             # Dashboard layout shell (chart grid)
      clinical_data_tab.html        # Sortable/searchable clinical attributes table
      cn_segments_tab.html          # Embedded IGV browser
      plots_tab.html                # Attribute scatter plot (Beta)
      charts/                       # One file per chart widget type
        cancer_type.html            # Table: cancer type frequencies
        clinical_group.html         # Table: AJCC staging group values
        pie_chart.html              # Generic reusable pie chart
        histogram.html              # Generic reusable bar/histogram (e.g. age)
        data_types.html             # Table: available molecular data profiles
        mutated_genes.html          # Table: gene mutation frequencies + OncoKB colors
        sv_genes.html               # Table: structural variant gene frequencies
        cna_genes.html              # Table: CNA gene frequencies (HOMDEL/AMP labels)
        treatment_patient.html      # Table: treatment counts per patient
        treatment_sample.html       # Table: treatment counts per sample (pre/post)
        scatter_tmb_fga.html        # Scatter: Mutation Count vs Fraction Genome Altered
        km_plot.html                # Mini Kaplan-Meier survival curve
```

## Conventions

- **Page templates** live at `{page}/page.html` and always `{% extends "base.html" %}`.
- **HTMX partials** (swap targets) live under `{page}/partials/`. Route handlers return
  these directly for partial swaps.
- **Shared partials** (used by 2+ pages) go in `shared/`. Never put shared content
  inside a page-specific directory.
- **Chart widgets** each get their own file under `{page}/partials/charts/` so they can
  be returned individually as HTMX swap targets when filters update.
- **New pages** follow the same pattern: add a `{page}/` directory, register a new
  router in `routes/{page}.py`, and include it in `app.py`.
