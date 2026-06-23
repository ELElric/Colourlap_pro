-- Initial schema for ColorLab Pro V1.1
-- Tables: projects, spectra, spectrum_points, optimizations

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

CREATE TABLE IF NOT EXISTS spectra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT,
    unit TEXT,
    source TEXT DEFAULT 'import',
    channel TEXT,
    wavelength_min REAL,
    wavelength_max REAL,
    wavelength_step REAL,
    point_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spectrum_points (
    spectrum_id INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    wavelength REAL NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (spectrum_id, idx),
    FOREIGN KEY (spectrum_id) REFERENCES spectra(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS optimizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT,
    target_xy_x REAL,
    target_xy_y REAL,
    result_json TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spectra_project ON spectra(project_id);
CREATE INDEX IF NOT EXISTS idx_points_spectrum ON spectrum_points(spectrum_id);
CREATE INDEX IF NOT EXISTS idx_optimizations_project ON optimizations(project_id);
