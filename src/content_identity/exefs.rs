//! Loader-visible files of an explicitly selected loose Switch ExeFS.
use super::*;

pub(super) fn selected(path: &Path, adapter: Option<&str>) -> bool {
    adapter == Some("eden_family") && path.file_name().is_some_and(|name| name == "main")
}

fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}

fn link_like(metadata: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        metadata.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

pub(super) fn source_member(entry: &Path, name: &str) -> io::Result<File> {
    let directory = entry.parent().unwrap_or_else(|| Path::new("."));
    if let Some(relative) = name.strip_prefix("exefs/") {
        return crate::path_safety::open_regular_member_no_follow(directory, relative);
    }
    if let Some(relative) = name.strip_prefix("romfs/") {
        let parent = directory
            .parent()
            .ok_or_else(|| invalid("ExeFS has no RomFS parent"))?;
        return crate::path_safety::open_regular_member_no_follow(
            parent,
            &format!("romfs/{relative}"),
        );
    }
    Err(invalid("invalid ExeFS graph member"))
}

fn add(names: &mut BTreeSet<String>, name: String) -> io::Result<()> {
    if !crate::path_safety::is_portable_relative_member(&name) {
        return Err(invalid("ExeFS member has an unsafe or nonportable name"));
    }
    names.insert(name);
    if names.len() >= crate::media_graph::MAX_GRAPH_MEMBERS
        || names.iter().map(String::len).sum::<usize>()
            > crate::media_graph::MAX_DECLARED_NAME_BYTES
    {
        return Err(invalid("ExeFS graph exceeds member/name bounds"));
    }
    Ok(())
}

fn collect_romfs(
    directory: &Path,
    prefix: &str,
    depth: usize,
    names: &mut BTreeSet<String>,
) -> io::Result<()> {
    if depth > 16 || link_like(&fs::symlink_metadata(directory)?) {
        return Err(invalid("RomFS directory is linked or exceeds depth limit"));
    }
    for entry in fs::read_dir(directory)? {
        let entry = entry?;
        let metadata = fs::symlink_metadata(entry.path())?;
        if link_like(&metadata) {
            return Err(invalid(
                "RomFS may not contain symbolic links or reparse points",
            ));
        }
        let name = entry
            .file_name()
            .into_string()
            .map_err(|_| invalid("RomFS name is not UTF-8"))?;
        let name = format!("{prefix}/{name}");
        if metadata.is_dir() {
            collect_romfs(&entry.path(), &name, depth + 1, names)?;
        } else if metadata.is_file() {
            add(names, name)?;
        } else {
            return Err(invalid("RomFS contains a nonregular member"));
        }
    }
    Ok(())
}

pub(super) fn members(entry: &Path) -> io::Result<Vec<String>> {
    crate::path_safety::open_regular_file_no_follow(entry)?;
    let directory = entry.parent().unwrap_or_else(|| Path::new("."));
    crate::path_safety::open_regular_member_no_follow(directory, "main.npdm")?;
    let mut names = BTreeSet::new();
    let mut romfs_count = 0;
    let mut fallback_icons = 0;
    let mut fallback_nacps = 0;
    for item in fs::read_dir(directory)? {
        let item = item?;
        let name = item
            .file_name()
            .into_string()
            .map_err(|_| invalid("ExeFS name is not UTF-8"))?;
        if name == "main" {
            continue;
        }
        let extension = Path::new(&name)
            .extension()
            .and_then(|value| value.to_str())
            .unwrap_or("");
        let module = matches!(name.as_str(), "rtld" | "sdk" | "main.npdm")
            || (name.starts_with("subsdk")
                && name.len() == 7
                && name.as_bytes()[6].is_ascii_digit());
        let asset = matches!(extension, "romfs" | "nacp" | "png" | "jpg" | "jpeg" | "bmp")
            || (name.starts_with("icon_") && extension == "dat");
        if module || asset {
            romfs_count += usize::from(extension == "romfs");
            fallback_icons += usize::from(matches!(extension, "png" | "jpg" | "jpeg" | "bmp"));
            fallback_nacps += usize::from(extension == "nacp" && name != "control.nacp");
            add(&mut names, format!("exefs/{name}"))?;
            source_member(entry, &format!("exefs/{name}"))?;
        }
    }
    if romfs_count > 1
        || fallback_icons > 1
        || (fallback_nacps > 1 && !directory.join("control.nacp").exists())
    {
        return Err(invalid(
            "ambiguous loose ExeFS fallback assets; select one RomFS/icon/control asset",
        ));
    }
    if romfs_count == 0 {
        if let Some(parent) = directory.parent() {
            let romfs = parent.join("romfs");
            match fs::symlink_metadata(&romfs) {
                Ok(metadata) if metadata.is_dir() => collect_romfs(&romfs, "romfs", 0, &mut names)?,
                Ok(_) => return Err(invalid("sibling RomFS must be an unlinked directory")),
                Err(error) if error.kind() == io::ErrorKind::NotFound => (),
                Err(error) => return Err(error),
            }
        }
    }
    Ok(std::iter::once("exefs/main".into()).chain(names).collect())
}

pub(super) fn identity(entry: &Path) -> io::Result<ContentIdentity> {
    let names = members(entry)?;
    let mut graph = Sha256::new();
    graph.update(b"emucap-exefs-graph-v1\0");
    let mut total = 0u64;
    let mut identities = Vec::new();
    for name in &names {
        let mut file = source_member(entry, name)?;
        let before = file.metadata()?;
        let size = before.len();
        total = total
            .checked_add(size)
            .filter(|size| *size <= crate::media_graph::MAX_GRAPH_BYTES)
            .ok_or_else(|| invalid("ExeFS graph byte limit exceeded"))?;
        if size > crate::media_graph::MAX_MEMBER_BYTES {
            return Err(invalid("ExeFS member byte limit exceeded"));
        }
        let mut digest = Sha256::new();
        let mut length = 0u64;
        let mut buffer = [0u8; 64 * 1024];
        loop {
            let count = file.read(&mut buffer)?;
            if count == 0 {
                break;
            }
            length += count as u64;
            if length > size {
                return Err(invalid("ExeFS member grew while hashing"));
            }
            digest.update(&buffer[..count]);
        }
        let after = file.metadata()?;
        if length != size || after.len() != size || before.modified().ok() != after.modified().ok()
        {
            return Err(invalid("ExeFS member changed while hashing"));
        }
        let digest = hex::encode(digest.finalize());
        graph.update((name.len() as u64).to_le_bytes());
        graph.update(name.as_bytes());
        graph.update(size.to_le_bytes());
        graph.update(digest.as_bytes());
        identities.push(ContentMemberIdentity {
            declared_name: name.clone(),
            size,
            digest,
        });
    }
    if names != members(entry)? {
        return Err(invalid("ExeFS member set changed while hashing"));
    }
    Ok(ContentIdentity {
        scope: ContentIdentityScope::ExeFsGraph,
        algorithm: ContentHashAlgorithm::Sha256,
        digest: hex::encode(graph.finalize()),
        size: total,
        members: identities,
    })
}
