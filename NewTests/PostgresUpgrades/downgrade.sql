-- this file is identical to https://orthanc.uclouvain.be/hg/orthanc-databases/raw-file/default/PostgreSQL/Plugins/SQL/Downgrades/Rev11ToRev10.sql

-- restore the old DeleteResource function

CREATE OR REPLACE FUNCTION DeleteResource(
    IN id BIGINT,
    OUT remaining_ancestor_resource_type INTEGER,
    OUT remaining_anncestor_public_id TEXT) AS $body$
DECLARE
    deleted_resource_row RECORD;
    deleted_parent_row RECORD;
    deleted_grand_parent_row RECORD;
    deleted_grand_grand_parent_row RECORD;
    locked_parent_row RECORD;
    locked_resource_row RECORD;
BEGIN
    SET client_min_messages = warning;   -- suppress NOTICE:  relation "deletedresources" already exists, skipping
    -- note: temporary tables are created at connection level -> they are likely to exist.
    -- These tables are used by the triggers
    CREATE TEMPORARY TABLE IF NOT EXISTS DeletedResources(
        resourceType INTEGER NOT NULL,
        publicId VARCHAR(64) NOT NULL
        );
    RESET client_min_messages;
    -- clear the temporary table in case it has been created earlier in the connection
    DELETE FROM DeletedResources;
    -- create/clear the DeletedFiles temporary table
    PERFORM CreateDeletedFilesTemporaryTable();
    -- Before deleting an object, we need to lock its parent until the end of the transaction to avoid that
    -- 2 threads deletes the last 2 instances of a series at the same time -> none of them would realize
    -- that they are deleting the last instance and the parent resources would not be deleted.
    -- Locking only the immediate parent is sufficient to prevent from this.
    SELECT * INTO locked_parent_row FROM resources WHERE internalid = (SELECT parentid FROM resources WHERE internalid = id) FOR UPDATE;
    -- Before deleting the resource itself, we lock it to retrieve the resourceType and to make sure not 2 connections try to
    -- delete it at the same time
    SELECT * INTO locked_resource_row FROM resources WHERE internalid = id FOR UPDATE;
    -- before delete the resource itself, we must delete its grand-grand-children, the grand-children and its children no to violate 
    -- the parentId referencing an existing primary key constrain.  This is actually implementing the ON DELETE CASCADE that was on the parentId in previous revisions.
    
    -- If this resource has grand-grand-children, delete them
    if locked_resource_row.resourceType < 1 THEN
        WITH grand_grand_children_to_delete AS (SELECT grandGrandChildLevel.internalId, grandGrandChildLevel.resourceType, grandGrandChildLevel.publicId
                                                FROM Resources childLevel
                                                INNER JOIN Resources grandChildLevel ON childLevel.internalId = grandChildLevel.parentId
                                                INNER JOIN Resources grandGrandChildLevel ON grandChildLevel.internalId = grandGrandChildLevel.parentId
                                                WHERE childLevel.parentId = id),
        
        deleted_grand_grand_children_rows AS (DELETE FROM Resources WHERE internalId IN (SELECT internalId FROM grand_grand_children_to_delete)
                                              RETURNING resourceType, publicId)
        INSERT INTO DeletedResources SELECT resourceType, publicId FROM deleted_grand_grand_children_rows; 
    END IF;
    -- If this resource has grand-children, delete them
    if locked_resource_row.resourceType < 2 THEN
        WITH grand_children_to_delete AS (SELECT grandChildLevel.internalId, grandChildLevel.resourceType, grandChildLevel.publicId
                                          FROM Resources childLevel
                                          INNER JOIN Resources grandChildLevel ON childLevel.internalId = grandChildLevel.parentId
                                          WHERE childLevel.parentId = id),
        
        deleted_grand_children_rows AS (DELETE FROM Resources WHERE internalId IN (SELECT internalId FROM grand_children_to_delete)
                                        RETURNING resourceType, publicId)
        INSERT INTO DeletedResources SELECT resourceType, publicId FROM deleted_grand_children_rows; 
    END IF;
    -- If this resource has children, delete them
    if locked_resource_row.resourceType < 3 THEN
        WITH deleted_children AS (DELETE FROM Resources 
                                  WHERE parentId = id
                                  RETURNING resourceType, publicId)
        INSERT INTO DeletedResources SELECT resourceType, publicId FROM deleted_children; 
    END IF;
    -- delete the resource itself
    DELETE FROM Resources WHERE internalId=id RETURNING * INTO deleted_resource_row;

    -- keep track of the deleted resources for C++ code
    INSERT INTO DeletedResources VALUES (deleted_resource_row.resourceType, deleted_resource_row.publicId);

    -- If this resource still has siblings, keep track of the remaining parent
    -- (a parent that must not be deleted but whose LastUpdate must be updated)
    SELECT resourceType, publicId INTO remaining_ancestor_resource_type, remaining_anncestor_public_id
        FROM Resources 
        WHERE internalId = deleted_resource_row.parentId
            AND EXISTS (SELECT 1 FROM Resources WHERE parentId = deleted_resource_row.parentId);
	IF deleted_resource_row.resourceType > 0 THEN
        -- If this resource is the latest child, delete the parent
        DELETE FROM Resources WHERE internalId = deleted_resource_row.parentId
                                    AND NOT EXISTS (SELECT 1 FROM Resources WHERE parentId = deleted_resource_row.parentId)
                                    RETURNING * INTO deleted_parent_row;
        IF FOUND THEN
            INSERT INTO DeletedResources VALUES (deleted_parent_row.resourceType, deleted_parent_row.publicId);
            IF deleted_parent_row.resourceType > 0 THEN
                -- If this resource is the latest child, delete the parent
                DELETE FROM Resources WHERE internalId = deleted_parent_row.parentId
                                    AND NOT EXISTS (SELECT 1 FROM Resources WHERE parentId = deleted_parent_row.parentId)
                                    RETURNING * INTO deleted_grand_parent_row;
                IF FOUND THEN
                    INSERT INTO DeletedResources VALUES (deleted_grand_parent_row.resourceType, deleted_grand_parent_row.publicId);
                    IF deleted_grand_parent_row.resourceType > 0 THEN
                        -- If this resource is the latest child, delete the parent
                        DELETE FROM Resources WHERE internalId = deleted_grand_parent_row.parentId
                                            AND NOT EXISTS (SELECT 1 FROM Resources WHERE parentId = deleted_grand_parent_row.parentId)
                                            RETURNING * INTO deleted_grand_parent_row;
                        IF FOUND THEN
                            INSERT INTO DeletedResources VALUES (deleted_grand_parent_row.resourceType, deleted_grand_parent_row.publicId);
                        END IF;
                    END IF;
                END IF;
            END IF;
        END IF;
    END IF;
END;

$body$ LANGUAGE plpgsql;

DROP INDEX IF EXISTS AttachedFilesUuid;

-- set the global properties that actually documents the DB version, revision and some of the capabilities
-- modify only the ones that have changed
DELETE FROM GlobalProperties WHERE property IN (4);
INSERT INTO GlobalProperties VALUES (4, 10); -- GlobalProperty_DatabasePatchLevel
